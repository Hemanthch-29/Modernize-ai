using Microsoft.Data.SqlClient;

// DailySalesReport — a tiny batch job for the separate "Reporting" application.
// It reads the shared ShopDB (vw_DailySales) and also writes to the shared Orders table,
// which is how ModernizeAI proves cross-application impact: changing Orders affects Reporting too.

const string connectionString =
    "Server=(localdb)\\MSSQLLocalDB;Database=ShopDB;Trusted_Connection=True;TrustServerCertificate=True";

using var conn = new SqlConnection(connectionString);
conn.Open();

// Read the daily sales totals (inline SQL over the shared view).
using (var read = new SqlCommand("SELECT SaleDate, Total FROM vw_DailySales ORDER BY SaleDate", conn))
using (var reader = read.ExecuteReader())
{
    Console.WriteLine("Date        Total");
    Console.WriteLine("----------  --------");
    while (reader.Read())
    {
        var date = ((DateTime)reader["SaleDate"]).ToString("yyyy-MM-dd");
        var total = (decimal)reader["Total"];
        Console.WriteLine($"{date}  {total,8:0.00}");
    }
}

// Reporting also writes back to the shared Orders table (no-op guard keeps the sample data intact).
using (var update = new SqlCommand("UPDATE Orders SET Status = Status WHERE 1 = 0", conn))
{
    update.ExecuteNonQuery();
}
