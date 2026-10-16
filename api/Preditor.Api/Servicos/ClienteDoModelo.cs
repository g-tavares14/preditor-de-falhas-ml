using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;
using Preditor.Api.Modelos;

namespace Preditor.Api.Servicos;

/// <summary>O microserviço do modelo não respondeu como devia (fora do ar, lento ou com erro). Vira 503 na API.</summary>
public class ModeloIndisponivelException(string mensagem, Exception? causa = null) : Exception(mensagem, causa);

/// <summary>Fala com o microserviço Python (<c>POST /prever</c>, <c>GET /saude</c>). Não calcula nada do modelo.</summary>
public class ClienteDoModelo(HttpClient http)
{
    // Os campos do Python são snake_case e minúsculos; os nomes das medições já vêm marcados com JsonPropertyName.
    private static readonly JsonSerializerOptions Opcoes = new(JsonSerializerDefaults.Web);

    public async Task<PrevisaoDoModelo> PreverAsync(Medicao medicao, CancellationToken ct = default)
    {
        // Corpo pronto em bytes (e não PostAsJsonAsync): este envia em pedaços (chunked), sem Content-Length, e o serviço Python
        // exige o tamanho para recusar corpos grandes antes de ler (411). Foi o teste de paridade com o Python real que achou isso.
        var corpoJson = new ByteArrayContent(JsonSerializer.SerializeToUtf8Bytes(new { medicoes = new[] { medicao } }, Opcoes));
        corpoJson.Headers.ContentType = new System.Net.Http.Headers.MediaTypeHeaderValue("application/json");
        var resposta = await Chamar(() => http.PostAsync("/prever", corpoJson, ct));
        var corpo = await Ler<RespostaDoPrever>(resposta, ct);

        // Uma medição enviada = uma previsão de volta. Qualquer outra coisa é um serviço que não é o que esperamos.
        if (corpo.Previsoes is not { Count: 1 } || corpo.Modelo is null)
            throw new ModeloIndisponivelException("O serviço do modelo respondeu num formato inesperado.");
        var previsao = corpo.Previsoes[0];
        return new PrevisaoDoModelo(previsao.Classe, previsao.Probabilidades, corpo.Modelo.Sha256);
    }

    /// <summary>A resposta do <c>/saude</c> como JSON cru: é o que <c>/api/modelo</c> mostra (a ficha do modelo carregado).</summary>
    public async Task<JsonElement> FichaAsync(CancellationToken ct = default)
    {
        var resposta = await Chamar(() => http.GetAsync("/saude", ct));
        return await Ler<JsonElement>(resposta, ct);
    }

    private static async Task<HttpResponseMessage> Chamar(Func<Task<HttpResponseMessage>> pedido)
    {
        try
        {
            var resposta = await pedido();
            if (!resposta.IsSuccessStatusCode)
                throw new ModeloIndisponivelException($"O serviço do modelo respondeu {(int)resposta.StatusCode}.");
            return resposta;
        }
        catch (HttpRequestException erro)
        {
            throw new ModeloIndisponivelException("Não consegui falar com o serviço do modelo.", erro);
        }
        catch (TaskCanceledException erro)
        {
            // Estouro do prazo do HttpClient (o cancelamento do próprio cliente passa direto, pelo OperationCanceledException).
            throw new ModeloIndisponivelException("O serviço do modelo demorou demais para responder.", erro);
        }
    }

    private static async Task<T> Ler<T>(HttpResponseMessage resposta, CancellationToken ct)
    {
        try
        {
            return await resposta.Content.ReadFromJsonAsync<T>(Opcoes, ct)
                   ?? throw new ModeloIndisponivelException("O serviço do modelo devolveu uma resposta vazia.");
        }
        catch (JsonException erro)
        {
            throw new ModeloIndisponivelException("O serviço do modelo devolveu algo que não é JSON.", erro);
        }
    }

    // --- O formato da resposta do Python -------------------------------------------------------------------------

    private record RespostaDoPrever(List<ItemDaPrevisao>? Previsoes, FichaDoModelo? Modelo);

    private record ItemDaPrevisao(string Classe, Dictionary<string, double> Probabilidades);

    private record FichaDoModelo([property: JsonPropertyName("sha256")] string Sha256);
}
