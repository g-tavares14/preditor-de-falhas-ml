using System.Threading.RateLimiting;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.RateLimiting;
using Microsoft.AspNetCore.Server.Kestrel.Core;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Options;
using Preditor.Api.Configuracao;
using Preditor.Api.Dados;
using Preditor.Api.Servicos;

// Números com ponto decimal em qualquer máquina: a cultura do sistema (pt-BR usa vírgula) não pode mudar como o formulário é lido.
System.Globalization.CultureInfo.DefaultThreadCurrentCulture = System.Globalization.CultureInfo.InvariantCulture;
System.Globalization.CultureInfo.DefaultThreadCurrentUICulture = System.Globalization.CultureInfo.InvariantCulture;

var builder = WebApplication.CreateBuilder(args);

// --- Serviços ------------------------------------------------------------------------------------------------
// Número tem de chegar como número: o padrão do ASP.NET aceitaria "3" (texto) como 3, e o serviço do modelo o recusa.
builder.Services.AddControllersWithViews().AddJsonOptions(o => o.JsonSerializerOptions.NumberHandling = System.Text.Json.Serialization.JsonNumberHandling.Strict);
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

// O microserviço do modelo: a URL e o prazo vêm da configuração, nunca do pedido. Tudo é lido na hora de usar (e não aqui no
// registro), para que a configuração dos testes e a do Compose, que chegam depois, também valham.
builder.Services.Configure<OpcoesDoServicoModelo>(builder.Configuration.GetSection(OpcoesDoServicoModelo.Secao));
builder.Services.Configure<OpcoesDeLimites>(builder.Configuration.GetSection(OpcoesDeLimites.Secao));
builder.Services.AddHttpClient<ClienteDoModelo>((provedor, http) =>
{
    var opcoes = provedor.GetRequiredService<IOptions<OpcoesDoServicoModelo>>().Value;
    http.BaseAddress = new Uri(opcoes.Url);
    http.Timeout = TimeSpan.FromSeconds(opcoes.TimeoutSegundos);
});

// SQLite em arquivo (SPEC-api-csharp.md): o banco é criado pelas migrações na partida.
builder.Services.AddDbContext<BancoDoPreditor>((provedor, o) =>
    o.UseSqlite(provedor.GetRequiredService<IConfiguration>().GetConnectionString("Banco")));
builder.Services.AddScoped<ServicoDePrevisao>();

// Erro de validação e serviço fora do ar saem como ProblemDetails (RFC 9457), não como página de erro.
builder.Services.AddProblemDetails();

// A API é pública e sem login: o que protege é o limite de pedidos por endereço e o de tamanho do corpo.
builder.Services.AddRateLimiter(_ => { }); // registra os serviços; as políticas vêm das opções abaixo
builder.Services.AddOptions<RateLimiterOptions>().Configure<IOptions<OpcoesDeLimites>>((limiter, limites) =>
{
    limiter.RejectionStatusCode = StatusCodes.Status429TooManyRequests;
    limiter.AddPolicy("previsoes", contexto => RateLimitPartition.GetFixedWindowLimiter(
        contexto.Connection.RemoteIpAddress?.ToString() ?? "desconhecido",
        _ => new FixedWindowRateLimiterOptions { PermitLimit = limites.Value.PedidosPorMinuto, Window = TimeSpan.FromMinutes(1) }));
});
builder.Services.AddOptions<KestrelServerOptions>().Configure<IOptions<OpcoesDeLimites>>((kestrel, limites) =>
    kestrel.Limits.MaxRequestBodySize = limites.Value.CorpoMaximoBytes);

var app = builder.Build();

// --- Banco ---------------------------------------------------------------------------------------------------
using (var escopo = app.Services.CreateScope())
{
    var banco = escopo.ServiceProvider.GetRequiredService<BancoDoPreditor>();
    // A pasta do arquivo do banco precisa existir antes de o SQLite criá-lo.
    var origem = new Microsoft.Data.Sqlite.SqliteConnectionStringBuilder(banco.Database.GetConnectionString()).DataSource;
    if (!string.IsNullOrEmpty(origem) && Path.GetDirectoryName(Path.GetFullPath(origem)) is { } pasta) Directory.CreateDirectory(pasta);
    banco.Database.Migrate();
}

// --- Pipeline ------------------------------------------------------------------------------------------------
// Qualquer ModeloIndisponivelException vira 503 com ProblemDetails (nunca uma previsão inventada).
app.UseExceptionHandler(erro => erro.Run(async contexto =>
{
    var excecao = contexto.Features.Get<Microsoft.AspNetCore.Diagnostics.IExceptionHandlerFeature>()?.Error;
    var indisponivel = excecao is ModeloIndisponivelException;
    // O detalhe de um erro interno fica só no log do servidor; o cliente recebe uma mensagem genérica.
    contexto.RequestServices.GetRequiredService<ILoggerFactory>().CreateLogger("Erros").LogError(excecao, "Falha em {Metodo} {Caminho}", contexto.Request.Method, contexto.Request.Path);
    contexto.Response.StatusCode = indisponivel ? StatusCodes.Status503ServiceUnavailable : StatusCodes.Status500InternalServerError;
    await contexto.Response.WriteAsJsonAsync(new ProblemDetails
    {
        Status = contexto.Response.StatusCode,
        Title = indisponivel ? "O serviço do modelo está indisponível." : "Erro interno.",
        // A mensagem de ModeloIndisponivelException é escrita por nós; as demais podem vazar detalhe e não saem.
        Detail = indisponivel ? excecao!.Message : null,
    });
}));
// Corpo grande demais = 413 antes de ler (o limite do Kestrel sozinho viraria 400 dentro do MVC).
app.Use(async (contexto, proximo) =>
{
    var limite = contexto.RequestServices.GetRequiredService<IOptions<OpcoesDeLimites>>().Value.CorpoMaximoBytes;
    if (contexto.Request.ContentLength > limite)
    {
        contexto.Response.StatusCode = StatusCodes.Status413PayloadTooLarge;
        await contexto.Response.WriteAsJsonAsync(new ProblemDetails { Status = 413, Title = $"O corpo passa de {limite} bytes." });
        return;
    }
    await proximo();
});
app.UseRateLimiter();
// O site do mapa (web/, sem alterar) é servido na raiz, junto com o wwwroot da própria API. A pasta vem da configuração:
// ao lado do código (../../web) em desenvolvimento e /app/web no contêiner.
var pastaWeb = Path.GetFullPath(app.Configuration["Web:Pasta"] ?? "../../web", app.Environment.ContentRootPath);
if (Directory.Exists(pastaWeb))
{
    app.Environment.WebRootFileProvider = new Microsoft.Extensions.FileProviders.CompositeFileProvider(
        app.Environment.WebRootFileProvider, new Microsoft.Extensions.FileProviders.PhysicalFileProvider(pastaWeb));
}
// O aovivo.json é gravado pelo serviço ao vivo (Python) num volume, fora do web/ da imagem; a página o pede em /dados/aovivo.json.
// Sem `Web:ArquivoAoVivo` configurado, o arquivo (se existir) sai do web/, como no desenvolvimento local.
var arquivoAoVivo = app.Configuration["Web:ArquivoAoVivo"];
if (!string.IsNullOrEmpty(arquivoAoVivo))
{
    app.MapGet("/dados/aovivo.json", (HttpContext contexto) =>
    {
        if (!File.Exists(arquivoAoVivo)) return Results.NotFound();
        contexto.Response.Headers.CacheControl = "no-cache";
        return Results.File(arquivoAoVivo, "application/json");
    });
}
app.UseDefaultFiles();
app.UseStaticFiles(new StaticFileOptions
{
    // O replay.json e o aovivo.json mudam sem o nome mudar: o navegador pergunta antes de reusar (como o servidor do Python faz).
    OnPrepareResponse = contexto => contexto.Context.Response.Headers.CacheControl = "no-cache",
});
app.UseSwagger();
app.UseSwaggerUI();
app.MapControllers().RequireRateLimiting("previsoes");
// O limite vale para as rotas da API e das páginas; o site estático (UseStaticFiles) vem antes e não conta.

app.Run();

// Torna o Program visível para os testes (WebApplicationFactory<Program>).
public partial class Program;
