using System.Net;
using System.Text.RegularExpressions;

namespace Preditor.Api.Tests;

public partial class PaginasTests
{
    [GeneratedRegex("name=\"__RequestVerificationToken\" type=\"hidden\" value=\"([^\"]+)\"")]
    private static partial Regex TokenAntiforgery();

    /// <summary>Abre o formulário (que traz o token e o cookie do antiforgery) e envia os campos como o navegador enviaria.</summary>
    private static async Task<HttpResponseMessage> EnviarFormulario(HttpClient cliente, Dictionary<string, string> campos)
    {
        var pagina = await cliente.GetStringAsync("/testar");
        var token = TokenAntiforgery().Match(pagina).Groups[1].Value;
        Assert.False(string.IsNullOrEmpty(token), "o formulário devia trazer o token antiforgery");
        campos["__RequestVerificationToken"] = token;
        return await cliente.PostAsync("/testar", new FormUrlEncodedContent(campos));
    }

    [Fact]
    public async Task Formulario_valido_mostra_a_classe_e_aparece_no_historico()
    {
        using var fabrica = new FabricaDeTeste(new ModeloFalso(classe: "RISCO"));
        using var cliente = fabrica.CreateClient();

        var resposta = await EnviarFormulario(cliente, new() { ["ZRobusto"] = "6.0", ["AumentoPct"] = "45", ["PerdaPct"] = "" });
        var html = await resposta.Content.ReadAsStringAsync();

        Assert.Equal(HttpStatusCode.OK, resposta.StatusCode);
        Assert.Contains("classe-RISCO", html);
        Assert.Contains("70.0%", html); // a probabilidade do modelo falso
        var historico = await cliente.GetStringAsync("/historico");
        Assert.Contains("formulario", historico);
        Assert.Contains("1 previsão guardadas", WebUtility.HtmlDecode(historico)); // o Razor escreve "ã" como entidade HTML
    }

    [Fact]
    public async Task Formulario_com_valor_fora_da_faixa_mostra_o_erro_na_coluna_e_nao_grava()
    {
        using var fabrica = new FabricaDeTeste(new ModeloFalso());
        using var cliente = fabrica.CreateClient();

        var html = await (await EnviarFormulario(cliente, new() { ["PerdaPct"] = "150" })).Content.ReadAsStringAsync();

        Assert.Contains("Tem de estar entre 0 e 100.", html);
        Assert.DoesNotContain("Previsão para daqui a 12 minutos", html);
        Assert.Contains("Ainda não há previsões", await cliente.GetStringAsync("/historico"));
    }

    [Fact]
    public async Task Formulario_com_modelo_fora_do_ar_explica_e_nao_mostra_previsao()
    {
        using var fabrica = new FabricaDeTeste(new ModeloFalso(derrubaConexao: true));
        using var cliente = fabrica.CreateClient();

        var html = await (await EnviarFormulario(cliente, new() { ["ZRobusto"] = "1" })).Content.ReadAsStringAsync();

        Assert.Contains("O serviço do modelo não respondeu", html);
        Assert.DoesNotContain("Previsão para daqui a 12 minutos", html);
    }

    [Fact]
    public async Task Formulario_sem_token_antiforgery_e_recusado()
    {
        using var fabrica = new FabricaDeTeste(new ModeloFalso());
        using var cliente = fabrica.CreateClient();

        var resposta = await cliente.PostAsync("/testar", new FormUrlEncodedContent(new Dictionary<string, string> { ["ZRobusto"] = "1" }));

        Assert.Equal(HttpStatusCode.BadRequest, resposta.StatusCode);
    }

    [Fact]
    public async Task Exemplo_preenche_o_formulario()
    {
        using var fabrica = new FabricaDeTeste(new ModeloFalso());
        using var cliente = fabrica.CreateClient();

        var html = await cliente.GetStringAsync("/testar?exemplo=pico");

        Assert.Contains("name=\"ZRobusto\" step=\"any\" value=\"6\"", html);
        Assert.Contains("name=\"AumentoPct\" step=\"any\" value=\"45\"", html);
    }

    [Fact]
    public async Task Swagger_publica_o_contrato_da_api()
    {
        using var fabrica = new FabricaDeTeste(new ModeloFalso());
        using var cliente = fabrica.CreateClient();

        var contrato = await cliente.GetStringAsync("/swagger/v1/swagger.json");

        Assert.Contains("/api/previsoes", contrato);
        Assert.Contains("/api/modelo", contrato);
    }
}
