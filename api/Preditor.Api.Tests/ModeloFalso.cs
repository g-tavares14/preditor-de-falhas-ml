using System.Net;
using System.Text;
using System.Text.Json;

namespace Preditor.Api.Tests;

/// <summary>Um "microserviço do modelo" de mentira: devolve sempre a mesma classe, ou falha, conforme o teste pede.</summary>
public class ModeloFalso(HttpStatusCode status = HttpStatusCode.OK, string classe = "RISCO", bool derrubaConexao = false) : HttpMessageHandler
{
    public List<string> Corpos { get; } = [];

    protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage pedido, CancellationToken ct)
    {
        if (derrubaConexao) throw new HttpRequestException("conexão recusada (de mentira)");
        if (pedido.Content is not null) Corpos.Add(await pedido.Content.ReadAsStringAsync(ct));

        var corpo = pedido.RequestUri!.AbsolutePath == "/saude"
            ? """{"status":"ok","modelo":{"familia":"random_forest","sha256":"abc","classes":["FALHA","OK","RISCO"]}}"""
            : JsonSerializer.Serialize(new
            {
                previsoes = new[] { new { classe, probabilidades = new { FALHA = 0.1, OK = 0.2, RISCO = 0.7 } } },
                modelo = new { sha256 = "abc" },
            });
        return new HttpResponseMessage(status) { Content = new StringContent(corpo, Encoding.UTF8, "application/json") };
    }
}
