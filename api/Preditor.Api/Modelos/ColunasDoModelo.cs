namespace Preditor.Api.Modelos;

/// <summary>Os nomes e as explicações das 10 colunas, para a página /testar (o texto de ajuda vem de <c>docs/</c> e da RFC §8).</summary>
public static class ColunasDoModelo
{
    public record Coluna(string Propriedade, string NomeNoModelo, string Titulo, string Ajuda, string Passo);

    public static readonly IReadOnlyList<Coluna> Todas =
    [
        new("ZRobusto", "z_robusto", "z robusto", "Quantos desvios (robustos) o RTT de agora está acima do normal da rota.", "any"),
        new("AumentoPct", "aumento_pct", "Aumento do RTT (%)", "Quanto o RTT de agora passa da mediana do baseline da rota.", "any"),
        new("JitterRelativo", "jitter_relativo", "Jitter relativo", "Jitter de agora dividido pelo jitter típico da rota.", "any"),
        new("PerdaPct", "perda_pct", "Perda (%)", "Pings sem resposta na rajada, de 0 a 100.", "any"),
        new("TimeoutAtual", "timeout_atual", "Timeout agora", "1 se a medição de agora deu timeout, senão 0.", "1"),
        new("N5Timeout", "n5_timeout", "Timeouts nas últimas 5", "De 0 a 5.", "1"),
        new("N5Aumento80", "n5_aumento80", "Aumentos ≥ 80% nas últimas 5", "De 0 a 5.", "1"),
        new("N5Moderado", "n5_moderado", "Aumentos moderados nas últimas 5", "De 0 a 5.", "1"),
        new("Min5Z", "min5_z", "Menor z nas últimas 5", "O menor z robusto da janela.", "any"),
        new("Media5Z", "media5_z", "Média do z nas últimas 5", "A média do z robusto da janela.", "any"),
    ];

    /// <summary>Casos prontos para a apresentação (os mesmos valores do <c>exemplo_de_uso.py</c> do modelo exportado).</summary>
    public static readonly IReadOnlyDictionary<string, (string Titulo, Medicao Medicao)> Exemplos = new Dictionary<string, (string, Medicao)>
    {
        ["estavel"] = ("Rota estável", new Medicao(0.3, 2.0, 1.1, 0.0, 0, 0, 0, 0, -0.5, -0.1)),
        ["pico"] = ("Pico de agora", new Medicao(6.0, 45.0, 2.0, 0.0, 0, 0, 0, 1, 0.1, 0.5)),
        ["timeout"] = ("Sem RTT nesta medição", new Medicao(null, null, null, 100.0, 1, 2, 0, 2, null, null)),
    };
}
