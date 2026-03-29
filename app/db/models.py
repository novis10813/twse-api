"""
SQLAlchemy ORM models for TWSE chip data.
Column naming follows FinMind dataset conventions for easy cross-reference.
"""
from sqlalchemy import BigInteger, Column, Date, DateTime, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class StockInstitutionalInvestors(Base):
    """
    個股三大法人買賣 — FinMind: TaiwanStockInstitutionalInvestorsBuySell
    TWSE source: T86
    name values: Foreign_Dealer / Foreign_Dealer_Self / Investment_Trust / Dealer_self / Dealer_Hedging
    """
    __tablename__ = "twse_stock_institutional_investors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    stock_id = Column(String(10), nullable=False)
    name = Column(String(50), nullable=False)
    buy = Column(BigInteger, nullable=False, default=0)
    sell = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("date", "stock_id", "name"),)


class TotalInstitutionalInvestors(Base):
    """
    整體市場三大法人買賣 — FinMind: TaiwanStockTotalInstitutionalInvestors
    TWSE source: BFI82U
    name values: 自營商(自行買賣) / 自營商(避險) / 投信 / 外資及陸資(不含外資自營商) / 外資自營商 / 合計
    """
    __tablename__ = "twse_total_institutional_investors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    name = Column(String(50), nullable=False)
    buy = Column(BigInteger, nullable=False, default=0)
    sell = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("date", "name"),)


class StockMargin(Base):
    """
    個股融資融券 — FinMind: TaiwanStockMarginPurchaseShortSale
    TWSE source: MI_MARGN (data0)
    """
    __tablename__ = "twse_stock_margin"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    stock_id = Column(String(10), nullable=False)
    MarginPurchaseBuy = Column(BigInteger, nullable=False, default=0)
    MarginPurchaseSell = Column(BigInteger, nullable=False, default=0)
    MarginPurchaseCashRepayment = Column(BigInteger, nullable=False, default=0)
    MarginPurchaseTodayBalance = Column(BigInteger, nullable=False, default=0)
    MarginPurchaseYesterdayBalance = Column(BigInteger, nullable=False, default=0)
    MarginPurchaseLimit = Column(BigInteger, nullable=False, default=0)
    ShortSaleBuy = Column(BigInteger, nullable=False, default=0)
    ShortSaleSell = Column(BigInteger, nullable=False, default=0)
    ShortSaleCashRepayment = Column(BigInteger, nullable=False, default=0)
    ShortSaleTodayBalance = Column(BigInteger, nullable=False, default=0)
    ShortSaleYesterdayBalance = Column(BigInteger, nullable=False, default=0)
    ShortSaleLimit = Column(BigInteger, nullable=False, default=0)
    OffsetLoanAndShort = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("date", "stock_id"),)


class TotalMargin(Base):
    """
    整體市場融資融券 — FinMind: TaiwanStockTotalMarginPurchaseShortSale
    TWSE source: MI_MARGN (data1)
    name values: MarginPurchase / ShortSale / MarginPurchaseMoney
    """
    __tablename__ = "twse_total_margin"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    name = Column(String(30), nullable=False)
    buy = Column(BigInteger, nullable=False, default=0)
    sell = Column(BigInteger, nullable=False, default=0)
    TodayBalance = Column(BigInteger, nullable=False, default=0)
    YesBalance = Column(BigInteger, nullable=False, default=0)
    Return = Column(BigInteger, nullable=False, default=0)  # 現金(現券)償還；Return 是 FinMind 欄位名，非 Python keyword
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("date", "name"),)


class StockShareholding(Base):
    """
    個股外資持股比例 — FinMind: TaiwanStockShareholding
    TWSE source: MI_QFIIS (selectType=ALLBUT0999)
    """
    __tablename__ = "twse_stock_shareholding"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    stock_id = Column(String(10), nullable=False)
    NumberOfSharesIssued = Column(BigInteger, nullable=False, default=0)
    ForeignInvestmentShares = Column(BigInteger, nullable=False, default=0)
    ForeignInvestmentSharesRatio = Column(Numeric(10, 6), nullable=False, default=0.0)
    ForeignInvestmentSharesWithoutDealers = Column(BigInteger, nullable=False, default=0)
    ForeignInvestmentSharesWithoutDealersRatio = Column(Numeric(10, 6), nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("date", "stock_id"),)
