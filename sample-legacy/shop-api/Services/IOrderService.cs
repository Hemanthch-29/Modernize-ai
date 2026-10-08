using ShopApi.Models;

namespace ShopApi.Services;

public enum CancelStatus
{
    Ok,
    NotFound,
    Conflict
}

public record CancelResult(CancelStatus Status, string? Error = null);

public interface IOrderService
{
    Task<Order?> GetOrder(int id);
    Task<CancelResult> CancelOrder(int id);
}
