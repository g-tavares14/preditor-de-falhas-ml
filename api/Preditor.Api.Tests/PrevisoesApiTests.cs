using System.Net;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Preditor.Api.Dados;

namespace Preditor.Api.Tests;

public class PrevisoesApiTests
{
    private const string MedicaoTipica = """{"z_robusto":6.0,"aumento_pct":45.0,"n5_moderado":1}""";

    private static StringContent Json(string texto) => new(texto, Encoding.UTF8, "application/json");

    private static async Task<int> ContarNoBanco(FabricaDeTeste fabrica)
    {
        using var escopo = fabrica.Services.CreateScope();
        return await escopo.ServiceProvider.GetRequiredService<BancoDoPreditor>().Previsoes.CountAsync();
    }

    [Fact]
    public async Task Pedido_valido_devolve_a_classe_do_modelo_e_grava_no_banco()
    {
        var modelo = new ModeloFalso(classe: "RISCO");
        using var fabrica = new FabricaDeTeste(modelo);
        using var cliente = fabrica.CreateClient();

        var resposta = await cliente.PostAsync("/api/previsoes", Json(MedicaoTipica));

        Assert.Equal(HttpStatusCode.OK, resposta.StatusCode);
        var corpo = await resposta.Content.ReadFromJsonAsync<JsonElement>();
        Assert.Equal("RISCO", corpo.GetProperty("classe").GetString());
        Assert.Equal(0.7, corpo.GetProperty("probabilidades").GetProperty("RISCO").GetDouble(), 12);
        Assert.Equal("abc", corpo.GetProperty("modeloSha256").GetString());
        Assert.Equal(1, await ContarNoBanco(fabrica));

        // O valor ausente chega ao modelo como null (e não como 0): imputar esconderia um timeout (RFC §8.3).
        var enviado = JsonDocument.Parse(Assert.Single(modelo.Corpos)).RootElement.GetProperty("medicoes")[0];
        Assert.Equal(JsonValueKind.Null, enviado.GetProperty("perda_pct").ValueKind);
        Assert.Equal(6.0, enviado.GetProperty("z_robusto").GetDouble());
    }

    [Fact]
    public async Task Historico_lista_da_mais_nova_para_a_mais_antiga()
    {
        using var fabrica = new FabricaDeTeste(new ModeloFalso());
        using var cliente = fabrica.CreateClient();
        await cliente.PostAsync("/api/previsoes", Json("""{"z_robusto":1.0}"""));
        await cliente.PostAsync("/api/previsoes", Json("""{"z_robusto":2.0}"""));

        var pagina = await cliente.GetFromJsonAsync<JsonElement>("/api/previsoes?pagina=1&tamanho=10");

        Assert.Equal(2, pagina.GetProperty("total").GetInt32());
        var itens = pagina.GetProperty("itens");
        Assert.Equal(2.0, itens[0].GetProperty("entrada").GetProperty("z_robusto").GetDouble());
        Assert.Equal(1.0, itens[1].GetProperty("entrada").GetProperty("z_robusto").GetDouble());
        Assert.Equal("api", itens[0].GetProperty("origem").GetString());
    }

    [Theory]
    [InlineData("""{"perda_pct":150}""", "perda_pct")]
    [InlineData("""{"timeout_atual":2}""", "timeout_atual")]
    [InlineData("""{"n5_timeout":9}""", "n5_timeout")]
    public async Task Coluna_fora_da_faixa_devolve_400_sem_chamar_o_modelo_nem_gravar(string corpo, string coluna)
    {
        var modelo = new ModeloFalso();
        using var fabrica = new FabricaDeTeste(modelo);
        using var cliente = fabrica.CreateClient();

        var resposta = await cliente.PostAsync("/api/previsoes", Json(corpo));

        Assert.Equal(HttpStatusCode.BadRequest, resposta.StatusCode);
        var problema = await resposta.Content.ReadFromJsonAsync<JsonElement>();
        Assert.True(problema.GetProperty("errors").TryGetProperty(coluna, out _), $"o erro devia citar '{coluna}'");
        Assert.Empty(modelo.Corpos);
        Assert.Equal(0, await ContarNoBanco(fabrica));
    }

    [Theory]
    [InlineData("""{"rtt":10.0}""")]                 // coluna que o modelo não usa
    [InlineData("""{"z_robusto":"3"}""")]            // texto no lugar de número
    [InlineData("""{"z_robusto":NaN}""")]            // JSON de verdade não tem NaN
    [InlineData("{nao e json")]
    public async Task Corpo_torto_devolve_400(string corpo)
    {
        using var fabrica = new FabricaDeTeste(new ModeloFalso());
        using var cliente = fabrica.CreateClient();

        var resposta = await cliente.PostAsync("/api/previsoes", Json(corpo));

        Assert.Equal(HttpStatusCode.BadRequest, resposta.StatusCode);
        Assert.Equal(0, await ContarNoBanco(fabrica));
    }

    [Theory]
    [InlineData(HttpStatusCode.InternalServerError, false)]
    [InlineData(HttpStatusCode.OK, true)]
    public async Task Modelo_fora_do_ar_devolve_503_e_nao_grava(HttpStatusCode statusDoModelo, bool derrubaConexao)
    {
        using var fabrica = new FabricaDeTeste(new ModeloFalso(statusDoModelo, derrubaConexao: derrubaConexao));
        using var cliente = fabrica.CreateClient();

        var resposta = await cliente.PostAsync("/api/previsoes", Json(MedicaoTipica));

        Assert.Equal(HttpStatusCode.ServiceUnavailable, resposta.StatusCode);
        Assert.Equal(0, await ContarNoBanco(fabrica));
    }

    [Fact]
    public async Task Pedidos_demais_por_minuto_devolvem_429()
    {
        using var fabrica = new FabricaDeTeste(new ModeloFalso(), new() { ["Limites:PedidosPorMinuto"] = "2" });
        using var cliente = fabrica.CreateClient();

        var codigos = new List<HttpStatusCode>();
        for (var i = 0; i < 3; i++) codigos.Add((await cliente.PostAsync("/api/previsoes", Json("{}"))).StatusCode);

        Assert.Equal([HttpStatusCode.OK, HttpStatusCode.OK, HttpStatusCode.TooManyRequests], codigos);
    }

    [Fact]
    public async Task Corpo_grande_demais_e_recusado()
    {
        using var fabrica = new FabricaDeTeste(new ModeloFalso(), new() { ["Limites:CorpoMaximoBytes"] = "100" });
        using var cliente = fabrica.CreateClient();

        var resposta = await cliente.PostAsync("/api/previsoes", Json("{\"z_robusto\":1.0," + new string(' ', 200) + "}"));

        Assert.Equal(HttpStatusCode.RequestEntityTooLarge, resposta.StatusCode);
    }

    [Fact]
    public async Task Saude_diz_qual_parte_esta_fora()
    {
        using var no_ar = new FabricaDeTeste(new ModeloFalso());
        using var fora = new FabricaDeTeste(new ModeloFalso(derrubaConexao: true));

        var bem = await no_ar.CreateClient().GetFromJsonAsync<JsonElement>("/api/saude");
        var mal = await fora.CreateClient().GetFromJsonAsync<JsonElement>("/api/saude");

        Assert.Equal("ok", bem.GetProperty("modelo").GetString());
        Assert.Equal("fora do ar", mal.GetProperty("modelo").GetString());
        Assert.Equal("ok", mal.GetProperty("api").GetString());
    }

    [Fact]
    public async Task Pagina_invalida_do_historico_devolve_400()
    {
        using var fabrica = new FabricaDeTeste(new ModeloFalso());
        using var cliente = fabrica.CreateClient();

        Assert.Equal(HttpStatusCode.BadRequest, (await cliente.GetAsync("/api/previsoes?pagina=0")).StatusCode);
        Assert.Equal(HttpStatusCode.BadRequest, (await cliente.GetAsync("/api/previsoes?tamanho=101")).StatusCode);
    }
}
