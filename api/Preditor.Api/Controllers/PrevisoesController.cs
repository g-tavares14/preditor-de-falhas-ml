using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Preditor.Api.Dados;
using Preditor.Api.Modelos;
using Preditor.Api.Servicos;

namespace Preditor.Api.Controllers;

[ApiController]
[Route("api/previsoes")]
public class PrevisoesController(ServicoDePrevisao servico, BancoDoPreditor banco) : ControllerBase
{
    private const int TamanhoMaximoDaPagina = 100;

    /// <summary>Prevê a classe de uma rota 12 minutos à frente e guarda o resultado.</summary>
    /// <response code="400">Alguma coluna fora da faixa, ou uma coluna que o modelo não usa.</response>
    /// <response code="503">O serviço do modelo está fora do ar.</response>
    [HttpPost]
    [ProducesResponseType<PrevisaoResposta>(StatusCodes.Status200OK)]
    [ProducesResponseType<ValidationProblemDetails>(StatusCodes.Status400BadRequest)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status503ServiceUnavailable)]
    public async Task<IActionResult> Criar([FromBody] Medicao medicao, CancellationToken ct)
    {
        var (erros, previsao) = await servico.PreverAsync(medicao, ServicoDePrevisao.OrigemApi, ct);
        return previsao is null ? ValidationProblem(new ValidationProblemDetails(erros)) : Ok(previsao.ComoResposta());
    }

    /// <summary>O histórico, da previsão mais nova para a mais antiga.</summary>
    [HttpGet]
    public async Task<ActionResult<PaginaDePrevisoes>> Listar([FromQuery] int pagina = 1, [FromQuery] int tamanho = 20, CancellationToken ct = default)
    {
        if (pagina < 1 || tamanho < 1 || tamanho > TamanhoMaximoDaPagina)
            return BadRequest(new ProblemDetails { Title = $"'pagina' começa em 1 e 'tamanho' vai de 1 a {TamanhoMaximoDaPagina}." });

        var total = await banco.Previsoes.CountAsync(ct);
        var itens = await banco.Previsoes.AsNoTracking()
            .OrderByDescending(p => p.CriadaEmUtc).ThenByDescending(p => p.Id)
            .Skip((pagina - 1) * tamanho).Take(tamanho)
            .ToListAsync(ct);
        return new PaginaDePrevisoes(pagina, tamanho, total, itens.Select(p => new ItemDoHistorico(p.ComoResposta(), p.Entrada(), p.Origem)).ToList());
    }
}

public record ItemDoHistorico(PrevisaoResposta Previsao, Medicao Entrada, string Origem);

public record PaginaDePrevisoes(int Pagina, int Tamanho, int Total, IReadOnlyList<ItemDoHistorico> Itens);
