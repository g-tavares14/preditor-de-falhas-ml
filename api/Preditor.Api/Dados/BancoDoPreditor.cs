using Microsoft.EntityFrameworkCore;

namespace Preditor.Api.Dados;

public class BancoDoPreditor(DbContextOptions<BancoDoPreditor> opcoes) : DbContext(opcoes)
{
    public DbSet<Previsao> Previsoes => Set<Previsao>();

    protected override void OnModelCreating(ModelBuilder modelo)
    {
        // A página de histórico lista da mais nova para a mais antiga: o índice evita varrer a tabela inteira.
        modelo.Entity<Previsao>().HasIndex(p => p.CriadaEmUtc);
        modelo.Entity<Previsao>().Property(p => p.Classe).HasMaxLength(10);
        modelo.Entity<Previsao>().Property(p => p.ModeloSha256).HasMaxLength(64);
        modelo.Entity<Previsao>().Property(p => p.Origem).HasMaxLength(20);
    }
}
