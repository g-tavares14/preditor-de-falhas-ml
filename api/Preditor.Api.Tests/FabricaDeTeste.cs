using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.DependencyInjection;

namespace Preditor.Api.Tests;

/// <summary>
/// A API inteira em memória, com um banco SQLite temporário e (quando pedido) um "serviço do modelo" falso no lugar do Python.
/// Cada fábrica tem o seu banco: um teste nunca vê as previsões de outro.
/// </summary>
public class FabricaDeTeste : WebApplicationFactory<Program>
{
    private readonly string _pasta = Directory.CreateTempSubdirectory("preditor-teste-").FullName;
    private readonly HttpMessageHandler? _modeloFalso;
    private readonly Dictionary<string, string?> _configuracao;

    public FabricaDeTeste(HttpMessageHandler? modeloFalso = null, Dictionary<string, string?>? configuracao = null)
    {
        _modeloFalso = modeloFalso;
        _configuracao = configuracao ?? [];
    }

    public string CaminhoDoBanco => Path.Combine(_pasta, "teste.db");

    protected override void ConfigureWebHost(IWebHostBuilder construtor)
    {
        construtor.UseSetting("ConnectionStrings:Banco", $"Data Source={CaminhoDoBanco}");
        foreach (var (chave, valor) in _configuracao) construtor.UseSetting(chave, valor);

        if (_modeloFalso is not null)
        {
            // Troca só o transporte do cliente do modelo: o código da API roda de verdade.
            construtor.ConfigureServices(servicos => servicos.AddHttpClient<Servicos.ClienteDoModelo>()
                .ConfigurePrimaryHttpMessageHandler(() => _modeloFalso));
        }
    }

    protected override void Dispose(bool descartando)
    {
        base.Dispose(descartando);
        try { Directory.Delete(_pasta, recursive: true); } catch (IOException) { /* o SQLite pode ainda segurar o arquivo: é temporário */ }
    }
}
