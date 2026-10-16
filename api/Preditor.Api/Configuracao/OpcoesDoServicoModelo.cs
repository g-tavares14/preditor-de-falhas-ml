namespace Preditor.Api.Configuracao;

/// <summary>Onde está o microserviço do modelo (seção "ServicoModelo" do appsettings). A rota vem daqui, nunca do pedido.</summary>
public class OpcoesDoServicoModelo
{
    public const string Secao = "ServicoModelo";

    public string Url { get; set; } = "http://127.0.0.1:8001";

    /// <summary>Segundos de espera pela resposta. A previsão leva milissegundos; mais que isso é serviço travado.</summary>
    public int TimeoutSegundos { get; set; } = 10;
}
