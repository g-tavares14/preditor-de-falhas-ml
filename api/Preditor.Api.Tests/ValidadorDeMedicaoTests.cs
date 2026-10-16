using Preditor.Api.Modelos;
using Preditor.Api.Servicos;

namespace Preditor.Api.Tests;

public class ValidadorDeMedicaoTests
{
    private static readonly Medicao Vazia = new(null, null, null, null, null, null, null, null, null, null);

    [Fact]
    public void Medicao_toda_ausente_e_valida() => Assert.Empty(ValidadorDeMedicao.Validar(Vazia));

    [Fact]
    public void Medicao_tipica_e_valida() =>
        Assert.Empty(ValidadorDeMedicao.Validar(new Medicao(6.0, 45.0, 2.0, 0.0, 0, 0, 0, 1, 0.1, 0.5)));

    [Theory]
    [InlineData(-0.1)]
    [InlineData(100.1)]
    [InlineData(double.NaN)]
    public void Perda_fora_de_0_a_100_e_recusada(double perda) =>
        Assert.Contains("perda_pct", ValidadorDeMedicao.Validar(Vazia with { PerdaPct = perda }).Keys);

    [Theory]
    [InlineData(0)]
    [InlineData(100)]
    [InlineData(37.5)]
    public void Perda_dentro_de_0_a_100_passa(double perda) => Assert.Empty(ValidadorDeMedicao.Validar(Vazia with { PerdaPct = perda }));

    [Theory]
    [InlineData(2)]
    [InlineData(0.5)]
    [InlineData(-1)]
    public void Timeout_so_aceita_0_ou_1(double timeout) =>
        Assert.Contains("timeout_atual", ValidadorDeMedicao.Validar(Vazia with { TimeoutAtual = timeout }).Keys);

    [Theory]
    [InlineData(6)]
    [InlineData(-1)]
    [InlineData(2.5)]
    public void Contagem_da_janela_e_inteiro_de_0_a_5(double contagem)
    {
        Assert.Contains("n5_timeout", ValidadorDeMedicao.Validar(Vazia with { N5Timeout = contagem }).Keys);
        Assert.Contains("n5_aumento80", ValidadorDeMedicao.Validar(Vazia with { N5Aumento80 = contagem }).Keys);
        Assert.Contains("n5_moderado", ValidadorDeMedicao.Validar(Vazia with { N5Moderado = contagem }).Keys);
    }

    [Theory]
    [InlineData(0)]
    [InlineData(5)]
    public void Contagem_nos_extremos_passa(double contagem) => Assert.Empty(ValidadorDeMedicao.Validar(Vazia with { N5Timeout = contagem }));

    [Fact]
    public void Metrica_relativa_infinita_e_recusada() =>
        Assert.Contains("z_robusto", ValidadorDeMedicao.Validar(Vazia with { ZRobusto = double.PositiveInfinity }).Keys);

    [Fact]
    public void Erros_de_varias_colunas_vem_juntos()
    {
        var erros = ValidadorDeMedicao.Validar(Vazia with { PerdaPct = 150, TimeoutAtual = 3 });
        Assert.Equal(["perda_pct", "timeout_atual"], erros.Keys.Order());
    }
}
