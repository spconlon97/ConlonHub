import sqlite3
from contextlib import closing
from decimal import Decimal
from pathlib import Path

from app.modules.tradingbot.models import (
    OrderSide,
    OrderStatus,
    PaperOrder,
)


class SqlitePaperOrderRepository:
    def __init__(self, database_path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        return sqlite3.connect(self.database_path)

    def _initialize(self):
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS paper_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity TEXT NOT NULL,
                    price TEXT NOT NULL,
                    status TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def add(self, order: PaperOrder):
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO paper_orders (
                    symbol,
                    side,
                    quantity,
                    price,
                    status
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    order.symbol,
                    order.side.value,
                    str(order.quantity),
                    str(order.price),
                    order.status.value,
                ),
            )
            connection.commit()

    def list_all(self):
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT symbol, side, quantity, price, status
                FROM paper_orders
                ORDER BY id
                """
            ).fetchall()

        return tuple(
            PaperOrder(
                symbol=row[0],
                side=OrderSide(row[1]),
                quantity=Decimal(row[2]),
                price=Decimal(row[3]),
                status=OrderStatus(row[4]),
            )
            for row in rows
        )