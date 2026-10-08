using Microsoft.AspNetCore.Mvc;
using ShopApi.Services;

namespace ShopApi.Controllers;

[ApiController]
[Route("api/orders")]
public class OrdersController : ControllerBase
{
    private readonly IOrderService _orderService;

    public OrdersController(IOrderService orderService)
    {
        _orderService = orderService;
    }

    [HttpGet("{id:int}")]
    public async Task<IActionResult> GetOrder(int id)
    {
        var order = await _orderService.GetOrder(id);
        if (order is null)
            return NotFound();
        return Ok(order);
    }

    [HttpPost("{id:int}/cancel")]
    public async Task<IActionResult> CancelOrder(int id)
    {
        var result = await _orderService.CancelOrder(id);
        return result.Status switch
        {
            CancelStatus.NotFound => NotFound(),
            CancelStatus.Conflict => Conflict(new { error = result.Error }),
            _ => NoContent()
        };
    }
}
