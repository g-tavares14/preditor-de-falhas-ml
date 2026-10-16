using Preditor.Api.Modelos;

namespace Preditor.Api.Dados;

/// <summary>Uma linha da tabela <c>Previsoes</c>: o que entrou, o que o modelo respondeu e qual modelo respondeu.</summary>
public class Previsao
{
    public long Id { get; set; }
    public DateTime CriadaEmUtc { get; set; }

    // As 10 entradas, anuláveis como no pedido (null = ausente).
    public double? ZRobusto { get; set; }
    public double? AumentoPct { get; set; }
    public double? JitterRelativo { get; set; }
    public double? PerdaPct { get; set; }
    public double? TimeoutAtual { get; set; }
    public double? N5Timeout { get; set; }
    public double? N5Aumento80 { get; set; }
    public double? N5Moderado { get; set; }
    public double? Min5Z { get; set; }
    public double? Media5Z { get; set; }

    public string Classe { get; set; } = "";
    public double ProbFalha { get; set; }
    public double ProbOk { get; set; }
    public double ProbRisco { get; set; }

    /// <summary>SHA-256 do <c>.joblib</c> que respondeu: prova qual modelo deu a classe.</summary>
    public string ModeloSha256 { get; set; } = "";

    /// <summary>De onde veio o pedido: "api" (POST direto) ou "formulario" (a página /testar).</summary>
    public string Origem { get; set; } = "";

    public static Previsao Criar(Medicao m, PrevisaoDoModelo previsao, string origem) => new()
    {
        CriadaEmUtc = DateTime.UtcNow,
        ZRobusto = m.ZRobusto, AumentoPct = m.AumentoPct, JitterRelativo = m.JitterRelativo, PerdaPct = m.PerdaPct,
        TimeoutAtual = m.TimeoutAtual, N5Timeout = m.N5Timeout, N5Aumento80 = m.N5Aumento80, N5Moderado = m.N5Moderado,
        Min5Z = m.Min5Z, Media5Z = m.Media5Z,
        Classe = previsao.Classe,
        ProbFalha = previsao.Probabilidades["FALHA"], ProbOk = previsao.Probabilidades["OK"], ProbRisco = previsao.Probabilidades["RISCO"],
        ModeloSha256 = previsao.ModeloSha256,
        Origem = origem,
    };

    public Medicao Entrada() => new(ZRobusto, AumentoPct, JitterRelativo, PerdaPct, TimeoutAtual, N5Timeout, N5Aumento80, N5Moderado, Min5Z, Media5Z);

    public PrevisaoResposta ComoResposta() => new(
        Id, CriadaEmUtc, Classe,
        new Dictionary<string, double> { ["FALHA"] = ProbFalha, ["OK"] = ProbOk, ["RISCO"] = ProbRisco },
        ModeloSha256);
}
