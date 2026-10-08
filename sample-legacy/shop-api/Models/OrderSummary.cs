namespace ShopApi.Models;

// Lightweight projection for the "orders belonging to a customer" list.
public class OrderSummary
{
    public int OrderId { get; set; }
    public string Status { get; set; } = string.Empty;
}
