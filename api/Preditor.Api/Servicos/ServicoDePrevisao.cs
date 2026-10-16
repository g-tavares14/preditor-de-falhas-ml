using Preditor.Api.Dados;
using Preditor.Api.Modelos;

namespace Preditor.Api.Servicos;

/// <summary>Valida, pergunta ao modelo e guarda a resposta. É o único caminho que grava uma previsão (API e página usam o mesmo).</summary>
public class ServicoDePrevisao(ClienteDoModelo modelo, BancoDoPreditor banco)
{
    public const string OrigemApi = "api";
    public const string OrigemFormulario = "formulario";

    /// <summary>Erros de validação por coluna, ou a previsão já gravada. Fora do ar = <see cref="ModeloIndisponivelException"/>.</summary>
    public async Task<(Dictionary<string, string[]> Erros, Previsao? Previsao)> PreverAsync(Medicao medicao, string origem, CancellationToken ct)
    {
        var erros = ValidadorDeMedicao.Validar(medicao);
        if (erros.Count > 0) return (erros, null);

        var resposta = await modelo.PreverAsync(medicao, ct);

        // Só grava o que o modelo respondeu: serviço fora do ar nunca deixa uma linha no histórico.
        var previsao = Previsao.Criar(medicao, resposta, origem);
        banco.Previsoes.Add(previsao);
        await banco.SaveChangesAsync(ct);
        return (erros, previsao);
    }
}
