using System.Diagnostics;
using System.Net;
using System.Net.Sockets;

namespace Preditor.Api.Tests;

/// <summary>
/// Sobe o microserviço Python de verdade (<c>uv run python -m preditor.servico_modelo</c>) numa porta livre e o derruba no fim.
/// É o que torna o teste de paridade uma prova: o modelo é o .joblib real, não um falso.
/// </summary>
public sealed class ServicoPythonReal : IAsyncLifetime
{
    private Process? _processo;

    public string Url { get; private set; } = "";

    public async Task InitializeAsync()
    {
        var porta = PortaLivre();
        Url = $"http://127.0.0.1:{porta}";
        _processo = Process.Start(new ProcessStartInfo("uv", $"run python -m preditor.servico_modelo --porta {porta}")
        {
            WorkingDirectory = RaizDoRepositorio(),
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        }) ?? throw new InvalidOperationException("Não consegui iniciar o 'uv'. Ele está no PATH?");
        // Se ninguém lê, o buffer do pipe enche e o Python trava ao escrever o log.
        _processo.OutputDataReceived += (_, _) => { };
        _processo.ErrorDataReceived += (_, _) => { };
        _processo.BeginOutputReadLine();
        _processo.BeginErrorReadLine();

        // O Python leva alguns segundos para importar o scikit-learn e abrir o modelo.
        using var http = new HttpClient();
        var limite = DateTime.UtcNow.AddSeconds(90);
        while (DateTime.UtcNow < limite)
        {
            if (_processo.HasExited) throw new InvalidOperationException($"O serviço Python terminou sozinho (código {_processo.ExitCode}).");
            try
            {
                if ((await http.GetAsync($"{Url}/saude")).IsSuccessStatusCode) return;
            }
            catch (HttpRequestException) { /* ainda subindo */ }
            await Task.Delay(500);
        }
        throw new TimeoutException("O serviço Python não respondeu ao /saude em 90 s.");
    }

    public Task DisposeAsync()
    {
        if (_processo is { HasExited: false }) _processo.Kill(entireProcessTree: true);
        _processo?.Dispose();
        return Task.CompletedTask;
    }

    private static int PortaLivre()
    {
        var escuta = new TcpListener(IPAddress.Loopback, 0);
        escuta.Start();
        var porta = ((IPEndPoint)escuta.LocalEndpoint).Port;
        escuta.Stop();
        return porta;
    }

    /// <summary>Sobe pastas até achar o pyproject.toml: o teste roda de api/Preditor.Api.Tests/bin/....</summary>
    private static string RaizDoRepositorio()
    {
        var pasta = new DirectoryInfo(AppContext.BaseDirectory);
        while (pasta is not null && !File.Exists(Path.Combine(pasta.FullName, "pyproject.toml"))) pasta = pasta.Parent;
        return pasta?.FullName ?? throw new DirectoryNotFoundException("Não achei o pyproject.toml acima de " + AppContext.BaseDirectory);
    }
}
