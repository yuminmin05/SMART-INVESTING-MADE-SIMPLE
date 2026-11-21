from django.db import models


class StockReturn(models.Model):
    """ผลตอบแทนรายปีที่ผู้ใช้แก้ไขได้ จัดเก็บในฐานข้อมูลโปรเจกต์"""

    symbol = models.CharField(max_length=10, unique=True)
    annual_return = models.FloatField(default=1.0)

    class Meta:
        ordering = ["symbol"]

    def __str__(self):
        return f"{self.symbol}: {self.annual_return}%"
