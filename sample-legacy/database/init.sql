-- init.sql — ShopDB schema, seed data, stored procedures and view.
-- Re-runnable: if ShopDB exists, force-close connections, drop it, then recreate.
-- Run with: sqlcmd -S "(localdb)\MSSQLLocalDB" -E -i init.sql   (sqlcmd handles the GO batch separators)

IF DB_ID('ShopDB') IS NOT NULL
BEGIN
    ALTER DATABASE ShopDB SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE ShopDB;
END
GO

CREATE DATABASE ShopDB;
GO

USE ShopDB;
GO

-- ---------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------
CREATE TABLE dbo.Customers (
    Id   INT           NOT NULL PRIMARY KEY,
    Name NVARCHAR(100) NOT NULL,
    Tier NVARCHAR(20)  NOT NULL   -- 'Standard' or 'Gold'
);

CREATE TABLE dbo.Products (
    Id    INT           NOT NULL PRIMARY KEY,
    Name  NVARCHAR(100) NOT NULL,
    Price DECIMAL(10,2) NOT NULL
);

CREATE TABLE dbo.Orders (
    Id         INT          NOT NULL PRIMARY KEY,
    CustomerId INT          NOT NULL REFERENCES dbo.Customers(Id),
    Status     NVARCHAR(20) NOT NULL,   -- 'New', 'Shipped', 'Cancelled'
    CreatedAt  DATETIME2    NOT NULL
);

CREATE TABLE dbo.OrderItems (
    Id        INT           NOT NULL PRIMARY KEY,
    OrderId   INT           NOT NULL REFERENCES dbo.Orders(Id),
    ProductId INT           NOT NULL REFERENCES dbo.Products(Id),
    Quantity  INT           NOT NULL,
    UnitPrice DECIMAL(10,2) NOT NULL
);
GO

-- ---------------------------------------------------------------------------
-- Seed data (must exist for the demo)
-- ---------------------------------------------------------------------------
INSERT INTO dbo.Customers (Id, Name, Tier) VALUES
    (1, 'Alice', 'Standard'),
    (2, 'Bob',   'Gold');

INSERT INTO dbo.Products (Id, Name, Price) VALUES
    (1, 'Keyboard', 150.00),
    (2, 'Monitor',  300.00),
    (3, 'Mouse',     25.00);

INSERT INTO dbo.Orders (Id, CustomerId, Status, CreatedAt) VALUES
    (1, 1, 'New',     '2026-10-01T09:00:00'),   -- Alice, Standard
    (2, 2, 'New',     '2026-10-01T10:00:00'),   -- Bob, Gold
    (3, 1, 'Shipped', '2026-10-02T11:00:00');   -- Alice, Shipped (cannot be cancelled)

INSERT INTO dbo.OrderItems (Id, OrderId, ProductId, Quantity, UnitPrice) VALUES
    (1, 1, 1, 1, 150.00),   -- Order 1: Keyboard x1
    (2, 1, 2, 1, 300.00),   -- Order 1: Monitor  x1  => subtotal 450.00
    (3, 2, 1, 1, 150.00),   -- Order 2: Keyboard x1
    (4, 2, 2, 1, 300.00),   -- Order 2: Monitor  x1  => subtotal 450.00 => Gold total 405.00
    (5, 3, 3, 2,  25.00);   -- Order 3: Mouse    x2  => subtotal  50.00
GO

-- ---------------------------------------------------------------------------
-- Stored procedures (the hidden business logic lives here)
-- ---------------------------------------------------------------------------

-- usp_GetOrderById: order header + customer name + items.
-- Total = SUM(Quantity * UnitPrice); if the customer is Gold, apply a 10% discount.
-- Returns two result sets: [1] header, [2] items.
CREATE PROCEDURE dbo.usp_GetOrderById
    @OrderId INT
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @Subtotal DECIMAL(10,2) =
        (SELECT SUM(oi.Quantity * oi.UnitPrice)
         FROM dbo.OrderItems oi
         WHERE oi.OrderId = @OrderId);

    DECLARE @Tier NVARCHAR(20) =
        (SELECT c.Tier
         FROM dbo.Orders o
         JOIN dbo.Customers c ON c.Id = o.CustomerId
         WHERE o.Id = @OrderId);

    DECLARE @Total DECIMAL(10,2) = ISNULL(@Subtotal, 0);
    IF @Tier = 'Gold'
        SET @Total = @Total * 0.90;   -- hidden rule: 10% discount for Gold customers

    -- [1] header
    SELECT
        o.Id     AS OrderId,
        c.Name   AS CustomerName,
        o.Status AS Status,
        @Total   AS Total
    FROM dbo.Orders o
    JOIN dbo.Customers c ON c.Id = o.CustomerId
    WHERE o.Id = @OrderId;

    -- [2] items
    SELECT
        p.Name       AS ProductName,
        oi.Quantity  AS Quantity,
        oi.UnitPrice AS UnitPrice
    FROM dbo.OrderItems oi
    JOIN dbo.Products p ON p.Id = oi.ProductId
    WHERE oi.OrderId = @OrderId
    ORDER BY oi.Id;
END
GO

-- usp_GetOrdersByCustomer: the orders belonging to one customer.
CREATE PROCEDURE dbo.usp_GetOrdersByCustomer
    @CustomerId INT
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        o.Id     AS OrderId,
        o.Status AS Status
    FROM dbo.Orders o
    WHERE o.CustomerId = @CustomerId
    ORDER BY o.Id;
END
GO

-- usp_CancelOrder: set Status = 'Cancelled'. Reject if the order is already Shipped.
CREATE PROCEDURE dbo.usp_CancelOrder
    @OrderId INT
AS
BEGIN
    SET NOCOUNT ON;

    IF EXISTS (SELECT 1 FROM dbo.Orders WHERE Id = @OrderId AND Status = 'Shipped')
        THROW 50001, 'Cannot cancel a shipped order.', 1;   -- hidden rule: shipped orders are final

    UPDATE dbo.Orders SET Status = 'Cancelled' WHERE Id = @OrderId;
END
GO

-- ---------------------------------------------------------------------------
-- View: totals per day (used by the Reporting app)
-- ---------------------------------------------------------------------------
CREATE VIEW dbo.vw_DailySales
AS
SELECT
    CAST(o.CreatedAt AS DATE)        AS SaleDate,
    SUM(oi.Quantity * oi.UnitPrice)  AS Total
FROM dbo.Orders o
JOIN dbo.OrderItems oi ON oi.OrderId = o.Id
WHERE o.Status <> 'Cancelled'
GROUP BY CAST(o.CreatedAt AS DATE);
GO
