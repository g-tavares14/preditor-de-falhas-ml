using System.Text.Json;
using Microsoft.AspNetCore.Mvc;
using Preditor.Api.Servicos;

namespace Preditor.Api.Controllers;

[ApiController]
public class ModeloController(ClienteDoModelo modelo) : ControllerBase
{
    /// <summary>A ficha do modelo carregado: família, parâmetros, colunas, classes e o SHA-256 do arquivo.</summary>
    [HttpGet("api/modelo")]
    public async Task<ActionResult<JsonElement>> Ficha(CancellationToken ct) => await modelo.FichaAsync(ct);

    /// <summary>A API está de pé e o serviço do modelo também? (200 nos dois casos; o campo diz qual está fora.)</summary>
    [HttpGet("api/saude")]
    public async Task<IActionResult> Saude(CancellationToken ct)
    {
        try
        {
            var ficha = await modelo.FichaAsync(ct);
            return Ok(new { api = "ok", modelo = "ok", sha256 = ficha.GetProperty("modelo").GetProperty("sha256").GetString() });
        }
        catch (ModeloIndisponivelException)
        {
            // O Compose usa este endereço como "a API está viva": o contêiner não deve ser reiniciado só porque o modelo caiu.
            return Ok(new { api = "ok", modelo = "fora do ar", sha256 = (string?)null });
        }
    }
}
