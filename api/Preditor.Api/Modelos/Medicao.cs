using System.Text.Json.Serialization;

namespace Preditor.Api.Modelos;

/// <summary>
/// As 10 colunas que a Random Forest recebe (as mesmas de <c>DadosModelo.colunas_ajustadas()</c>, na ordem do modelo).
/// Valor ausente fica ausente (<c>null</c>): o modelo o aceita, e imputar um zero esconderia um timeout (RFC §8.3).
/// </summary>
// Coluna que o modelo não usa é recusada (400), em vez de ser ignorada em silêncio.
[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow)]
public record Medicao(
    [property: JsonPropertyName("z_robusto")] double? ZRobusto,
    [property: JsonPropertyName("aumento_pct")] double? AumentoPct,
    [property: JsonPropertyName("jitter_relativo")] double? JitterRelativo,
    [property: JsonPropertyName("perda_pct")] double? PerdaPct,
    [property: JsonPropertyName("timeout_atual")] double? TimeoutAtual,
    [property: JsonPropertyName("n5_timeout")] double? N5Timeout,
    [property: JsonPropertyName("n5_aumento80")] double? N5Aumento80,
    [property: JsonPropertyName("n5_moderado")] double? N5Moderado,
    [property: JsonPropertyName("min5_z")] double? Min5Z,
    [property: JsonPropertyName("media5_z")] double? Media5Z);
