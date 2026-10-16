using System.Net.Http.Json;
using System.Text;
using System.Text.Json;

namespace Preditor.Api.Tests;

/// <summary>
/// A prova de que o C# não muda nada: a API, falando com o modelo Python de verdade, devolve em cada linha da amostra
/// (gerada por <c>python -m preditor_analise.conferir_servico</c>, com as linhas de NaN) a mesma classe e as mesmas probabilidades
/// que o modelo recarregado deu no Python.
/// </summary>
public class ParidadeTests : IClassFixture<ServicoPythonReal>
{
    private const double Tolerancia = 1e-9;
    private readonly ServicoPythonReal _python;

    public ParidadeTests(ServicoPythonReal python) => _python = python;

    [Fact]
    public async Task Api_devolve_o_que_o_modelo_python_devolveu_em_todas_as_linhas_da_amostra()
    {
        var arquivo = Path.Combine(AppContext.BaseDirectory, "Fixtures", "paridade.json");
        var amostra = JsonDocument.Parse(await File.ReadAllTextAsync(arquivo)).RootElement;
        var linhas = amostra.GetProperty("amostra");
        Assert.True(linhas.GetArrayLength() >= 300, "a amostra de paridade devia ter ~300 linhas");

        using var fabrica = new FabricaDeTeste(configuracao: new()
        {
            ["ServicoModelo:Url"] = _python.Url,
            ["Limites:PedidosPorMinuto"] = "100000", // a amostra inteira passa pela API em poucos segundos
        });
        using var cliente = fabrica.CreateClient();

        var diferentes = new List<string>();
        var comNan = 0;
        var classes = new HashSet<string>();
        var indice = 0;
        foreach (var linha in linhas.EnumerateArray())
        {
            var entrada = linha.GetProperty("entrada");
            if (entrada.EnumerateObject().Any(c => c.Value.ValueKind == JsonValueKind.Null)) comNan++;

            var resposta = await cliente.PostAsync("/api/previsoes", new StringContent(entrada.GetRawText(), Encoding.UTF8, "application/json"));
            Assert.True(resposta.IsSuccessStatusCode, $"linha {indice}: {(int)resposta.StatusCode} {await resposta.Content.ReadAsStringAsync()}");
            var recebido = await resposta.Content.ReadFromJsonAsync<JsonElement>();

            var esperado = linha.GetProperty("esperado");
            var classe = recebido.GetProperty("classe").GetString()!;
            classes.Add(classe);
            if (classe != esperado.GetProperty("classe").GetString()) diferentes.Add($"linha {indice}: classe {classe}");
            foreach (var p in esperado.GetProperty("probabilidades").EnumerateObject())
            {
                var delta = Math.Abs(recebido.GetProperty("probabilidades").GetProperty(p.Name).GetDouble() - p.Value.GetDouble());
                if (delta > Tolerancia) diferentes.Add($"linha {indice}: {p.Name} difere em {delta:E2}");
            }
            indice++;
        }

        Assert.Empty(diferentes);
        Assert.True(comNan >= 100, $"a amostra devia ter ao menos 100 linhas com NaN (tem {comNan})");
        Assert.Equal(["FALHA", "OK", "RISCO"], classes.Order());

        // A API devolve o SHA-256 do arquivo que o Python abriu; é o mesmo que a amostra registrou.
        var ficha = await cliente.GetFromJsonAsync<JsonElement>("/api/modelo");
        Assert.Equal(amostra.GetProperty("modelo_sha256").GetString(), ficha.GetProperty("modelo").GetProperty("sha256").GetString());
    }
}
