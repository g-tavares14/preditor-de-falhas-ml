namespace Preditor.Api.Configuracao;

/// <summary>Os limites da API pública (seção "Limites" do appsettings): quantos pedidos por minuto e qual o maior corpo.</summary>
public class OpcoesDeLimites
{
    public const string Secao = "Limites";

    public int PedidosPorMinuto { get; set; } = 60;

    public long CorpoMaximoBytes { get; set; } = 16_384;
}
