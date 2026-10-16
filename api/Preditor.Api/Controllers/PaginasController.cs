using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Preditor.Api.Dados;
using Preditor.Api.Modelos;
using Preditor.Api.Servicos;

namespace Preditor.Api.Controllers;

/// <summary>As duas páginas em Razor (MVC): o formulário para testar o modelo e o histórico guardado no banco.</summary>
public class PaginasController(ServicoDePrevisao servico, BancoDoPreditor banco) : Controller
{
    private const int PrevisoesPorPagina = 25;

    [HttpGet("testar")]
    public IActionResult Testar(string? exemplo)
    {
        // Um exemplo escolhido preenche o formulário; sem exemplo, o formulário vem vazio (tudo ausente).
        var entrada = exemplo is not null && ColunasDoModelo.Exemplos.TryGetValue(exemplo, out var pronto) ? pronto.Medicao : null;
        return View(new TestarViewModel(entrada));
    }

    [HttpPost("testar")]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> Testar([FromForm] Medicao entrada, CancellationToken ct)
    {
        try
        {
            var (erros, previsao) = await servico.PreverAsync(entrada, ServicoDePrevisao.OrigemFormulario, ct);
            return View(new TestarViewModel(entrada, previsao, erros));
        }
        catch (ModeloIndisponivelException erro)
        {
            // A página explica; nunca mostra uma previsão que não veio do modelo.
            return View(new TestarViewModel(entrada, Falha: erro.Message));
        }
    }

    [HttpGet("historico")]
    public async Task<IActionResult> Historico(int pagina = 1, CancellationToken ct = default)
    {
        pagina = Math.Max(1, pagina);
        var total = await banco.Previsoes.CountAsync(ct);
        var itens = await banco.Previsoes.AsNoTracking()
            .OrderByDescending(p => p.CriadaEmUtc).ThenByDescending(p => p.Id)
            .Skip((pagina - 1) * PrevisoesPorPagina).Take(PrevisoesPorPagina)
            .ToListAsync(ct);
        return View(new HistoricoViewModel(itens, pagina, total, PrevisoesPorPagina));
    }
}

public record TestarViewModel(Medicao? Entrada, Previsao? Resultado = null, Dictionary<string, string[]>? Erros = null, string? Falha = null);

public record HistoricoViewModel(IReadOnlyList<Previsao> Itens, int Pagina, int Total, int PorPagina)
{
    public int TotalDePaginas => Math.Max(1, (int)Math.Ceiling(Total / (double)PorPagina));
}
