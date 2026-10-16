namespace Preditor.Api.Modelos;

/// <summary>O que o microserviço Python devolve para uma medição: a classe 12 minutos à frente e as probabilidades.</summary>
public record PrevisaoDoModelo(string Classe, IReadOnlyDictionary<string, double> Probabilidades, string ModeloSha256);

/// <summary>A resposta pública de <c>POST /api/previsoes</c>.</summary>
public record PrevisaoResposta(
    long Id,
    DateTime CriadaEmUtc,
    string Classe,
    IReadOnlyDictionary<string, double> Probabilidades,
    string ModeloSha256);
