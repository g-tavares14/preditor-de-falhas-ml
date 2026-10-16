using Preditor.Api.Modelos;

namespace Preditor.Api.Servicos;

/// <summary>
/// As faixas que uma medição de verdade pode ter. O microserviço só confere o formato; os limites ficam aqui, na borda pública.
/// </summary>
public static class ValidadorDeMedicao
{
    private const int JanelaDeMedicoes = 5; // config.JANELA: as colunas n5_* contam entre 0 e 5 medições

    /// <summary>Os erros por coluna (vazio = medição válida), no formato que o <c>ValidationProblem</c> do ASP.NET entende.</summary>
    public static Dictionary<string, string[]> Validar(Medicao medicao)
    {
        var erros = new Dictionary<string, string[]>();

        Faixa(erros, "perda_pct", medicao.PerdaPct, 0, 100);
        Binaria(erros, "timeout_atual", medicao.TimeoutAtual);
        foreach (var (nome, valor) in new[]
                 {
                     ("n5_timeout", medicao.N5Timeout),
                     ("n5_aumento80", medicao.N5Aumento80),
                     ("n5_moderado", medicao.N5Moderado),
                 })
        {
            Inteiro(erros, nome, valor, 0, JanelaDeMedicoes);
        }

        // As demais são métricas relativas sem teto fixo; só têm de ser números finitos.
        Finito(erros, "z_robusto", medicao.ZRobusto);
        Finito(erros, "aumento_pct", medicao.AumentoPct);
        Finito(erros, "jitter_relativo", medicao.JitterRelativo);
        Finito(erros, "min5_z", medicao.Min5Z);
        Finito(erros, "media5_z", medicao.Media5Z);

        return erros;
    }

    private static void Finito(Dictionary<string, string[]> erros, string coluna, double? valor)
    {
        if (valor is double v && !double.IsFinite(v)) erros[coluna] = ["Tem de ser um número finito ou null."];
    }

    private static void Faixa(Dictionary<string, string[]> erros, string coluna, double? valor, double minimo, double maximo)
    {
        if (valor is double v && !(double.IsFinite(v) && v >= minimo && v <= maximo))
            erros[coluna] = [$"Tem de estar entre {minimo} e {maximo}."];
    }

    private static void Binaria(Dictionary<string, string[]> erros, string coluna, double? valor)
    {
        if (valor is double v && v != 0 && v != 1) erros[coluna] = ["Tem de ser 0 ou 1."];
    }

    private static void Inteiro(Dictionary<string, string[]> erros, string coluna, double? valor, int minimo, int maximo)
    {
        if (valor is double v && !(double.IsFinite(v) && v == Math.Floor(v) && v >= minimo && v <= maximo))
            erros[coluna] = [$"Tem de ser um inteiro de {minimo} a {maximo}."];
    }
}
