using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Preditor.Api.Dados.Migracoes
{
    /// <inheritdoc />
    public partial class Inicial : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "Previsoes",
                columns: table => new
                {
                    Id = table.Column<long>(type: "INTEGER", nullable: false)
                        .Annotation("Sqlite:Autoincrement", true),
                    CriadaEmUtc = table.Column<DateTime>(type: "TEXT", nullable: false),
                    ZRobusto = table.Column<double>(type: "REAL", nullable: true),
                    AumentoPct = table.Column<double>(type: "REAL", nullable: true),
                    JitterRelativo = table.Column<double>(type: "REAL", nullable: true),
                    PerdaPct = table.Column<double>(type: "REAL", nullable: true),
                    TimeoutAtual = table.Column<double>(type: "REAL", nullable: true),
                    N5Timeout = table.Column<double>(type: "REAL", nullable: true),
                    N5Aumento80 = table.Column<double>(type: "REAL", nullable: true),
                    N5Moderado = table.Column<double>(type: "REAL", nullable: true),
                    Min5Z = table.Column<double>(type: "REAL", nullable: true),
                    Media5Z = table.Column<double>(type: "REAL", nullable: true),
                    Classe = table.Column<string>(type: "TEXT", maxLength: 10, nullable: false),
                    ProbFalha = table.Column<double>(type: "REAL", nullable: false),
                    ProbOk = table.Column<double>(type: "REAL", nullable: false),
                    ProbRisco = table.Column<double>(type: "REAL", nullable: false),
                    ModeloSha256 = table.Column<string>(type: "TEXT", maxLength: 64, nullable: false),
                    Origem = table.Column<string>(type: "TEXT", maxLength: 20, nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Previsoes", x => x.Id);
                });

            migrationBuilder.CreateIndex(
                name: "IX_Previsoes_CriadaEmUtc",
                table: "Previsoes",
                column: "CriadaEmUtc");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "Previsoes");
        }
    }
}
