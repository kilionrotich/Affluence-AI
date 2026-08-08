"""Commission Forecasting Service

Provides commission forecasting, trend analysis, and predictive insights
using statistical methods and historical data analysis.
"""
from datetime import datetime, timedelta
from typing import Any

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Commission, Click, Purchase


class CommissionForecaster:
    """Forecasts commission earnings and provides trend analysis."""

    def __init__(self, db: Session):
        self.db = db

    def forecast_commissions(
        self, period: str = "monthly", months: int = 3
    ) -> dict[str, Any]:
        """Forecast commissions for upcoming periods.

        Uses linear regression on historical commission data to predict
        future earnings.
        """
        # Get historical commission data aggregated by period
        historical = self._get_historical_commissions()

        if len(historical) < 2:
            return {
                "forecast": [],
                "confidence": "low",
                "message": "Insufficient historical data for forecasting. Need at least 2 data points.",
                "historical_data_points": len(historical),
            }

        # Extract x (time periods) and y (earnings)
        x = np.array(range(len(historical)))
        y = np.array([h["total"] for h in historical])

        # Perform linear regression
        slope, intercept = np.polyfit(x, y, 1)

        # Generate forecast
        forecast = []
        last_period = len(historical) - 1
        base_date = datetime.utcnow()

        for i in range(1, months + 1):
            period_idx = last_period + i
            predicted = slope * period_idx + intercept

            # Calculate confidence interval (wider for further periods)
            confidence_interval = max(predicted * 0.3, predicted * 0.1 * i)
            lower_bound = max(0, predicted - confidence_interval)
            upper_bound = predicted + confidence_interval

            # Calculate date for the period
            if period == "weekly":
                forecast_date = base_date + timedelta(weeks=i)
                period_label = forecast_date.strftime("%Y-W%U")
            else:  # monthly
                month = base_date.month + i
                year = base_date.year + (month - 1) // 12
                month = ((month - 1) % 12) + 1
                forecast_date = datetime(year, month, 1)
                period_label = forecast_date.strftime("%Y-%m")

            forecast.append({
                "period": period_label,
                "predicted_earnings": round(max(0, predicted), 2),
                "lower_bound": round(lower_bound, 2),
                "upper_bound": round(upper_bound, 2),
                "confidence": "high" if i <= 2 else "medium",
            })

        # Calculate trend direction
        trend_direction = "upward" if slope > 0 else ("downward" if slope < 0 else "stable")

        return {
            "forecast": forecast,
            "trend_direction": trend_direction,
            "trend_strength": round(abs(slope), 4),
            "confidence": "high" if len(historical) >= 6 else "medium" if len(historical) >= 3 else "low",
            "historical_data_points": len(historical),
            "forecast_periods": months,
            "period_type": period,
            "generated_at": datetime.utcnow().isoformat(),
        }

    def get_trends(self) -> dict[str, Any]:
        """Get commission trends and insights."""
        total_commissions = (
            self.db.scalar(select(func.count(Commission.id))) or 0
        )
        total_earnings = (
            self.db.scalar(
                select(func.coalesce(func.sum(Commission.amount), 0))
            ) or 0
        )

        # Get last 30 days data
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_earnings = (
            self.db.scalar(
                select(func.coalesce(func.sum(Commission.amount), 0)).where(
                    Commission.created_at >= thirty_days_ago
                )
            ) or 0
        )

        # Get previous 30 days for comparison
        sixty_days_ago = datetime.utcnow() - timedelta(days=60)
        previous_earnings = (
            self.db.scalar(
                select(func.coalesce(func.sum(Commission.amount), 0)).where(
                    Commission.created_at >= sixty_days_ago,
                    Commission.created_at < thirty_days_ago,
                )
            ) or 0
        )

        # Calculate period-over-period change
        if previous_earnings > 0:
            change_pct = round(
                ((recent_earnings - previous_earnings) / previous_earnings) * 100, 1
            )
        else:
            change_pct = 100.0 if recent_earnings > 0 else 0.0

        # Click-through trends
        total_clicks = self.db.scalar(select(func.count(Click.id))) or 0
        recent_clicks = (
            self.db.scalar(
                select(func.count(Click.id)).where(
                    Click.clicked_at >= thirty_days_ago
                )
            ) or 0
        )

        # Conversion rate
        conversions = (
            self.db.scalar(
                select(func.count(Purchase.id)).where(
                    Purchase.click_id.isnot(None)
                )
            ) or 0
        )
        conversion_rate = round(
            (conversions / total_clicks * 100) if total_clicks > 0 else 0, 2
        )

        return {
            "total_earnings": float(total_earnings),
            "total_commissions": total_commissions,
            "recent_30_days_earnings": float(recent_earnings),
            "previous_30_days_earnings": float(previous_earnings),
            "period_change_pct": change_pct,
            "trend": "growing" if change_pct > 5 else ("declining" if change_pct < -5 else "stable"),
            "total_clicks": total_clicks,
            "recent_30_days_clicks": recent_clicks,
            "conversions": conversions,
            "conversion_rate": conversion_rate,
            "average_commission_value": (
                round(float(total_earnings) / total_commissions, 2)
                if total_commissions > 0
                else 0
            ),
            "current_pace": float(recent_earnings),
            "projected_monthly": round(float(recent_earnings) * 1.1, 2),
        }

    def get_summary(self) -> dict[str, Any]:
        """Get a comprehensive summary of forecast insights."""
        trends = self.get_trends()
        forecast_data = self.forecast_commissions(months=3)

        # Calculate best and worst case scenarios
        monthly_avg = (
            trends.get("recent_30_days_earnings", 0)
        )

        return {
            "current_month_earnings": monthly_avg,
            "next_month_projection": (
                forecast_data["forecast"][0]["predicted_earnings"]
                if forecast_data.get("forecast")
                else monthly_avg
            ),
            "quarter_projection": (
                sum(f["predicted_earnings"] for f in forecast_data["forecast"])
                if forecast_data.get("forecast")
                else monthly_avg * 3
            ),
            "trend": trends.get("trend", "stable"),
            "period_change_pct": trends.get("period_change_pct", 0),
            "conversion_rate": trends.get("conversion_rate", 0),
            "average_commission": trends.get("average_commission_value", 0),
            "confidence": forecast_data.get("confidence", "low"),
            "insights": self._generate_insights(trends, forecast_data),
        }

    def _generate_insights(
        self, trends: dict, forecast_data: dict
    ) -> list[str]:
        """Generate human-readable insights from the data."""
        insights = []

        # Trend insights
        if trends.get("trend") == "growing":
            insights.append(
                f"Your affiliate earnings are growing at {trends['period_change_pct']}% "
                "period-over-period. Keep up the good work!"
            )
        elif trends.get("trend") == "declining":
            insights.append(
                f"Your earnings have declined {abs(trends['period_change_pct'])}% "
                "recently. Consider increasing content output or trying new products."
            )
        else:
            insights.append(
                "Your earnings are stable. Try expanding to new affiliate networks "
                "or increasing content frequency to boost growth."
            )

        # Conversion rate insights
        if trends.get("conversion_rate", 0) < 1:
            insights.append(
                f"Your conversion rate ({trends['conversion_rate']}%) is below 1%. "
                "Consider optimizing your affiliate link placements and content quality."
            )
        elif trends.get("conversion_rate", 0) > 5:
            insights.append(
                f"Excellent conversion rate of {trends['conversion_rate']}%! "
                "Your audience trusts your recommendations."
            )

        # Forecast insights
        if forecast_data.get("forecast"):
            next_month = forecast_data["forecast"][0]
            if next_month["predicted_earnings"] > trends.get("recent_30_days_earnings", 0):
                insights.append(
                    f"We project {forecast_data['forecast_periods']}-month "
                    f"earnings of ${sum(f['predicted_earnings'] for f in forecast_data['forecast']):.2f}. "
                    "Consider scaling up your efforts."
                )
            else:
                insights.append(
                    "Consider diversifying your product portfolio to increase "
                    "earnings potential."
                )

        # Average commission insights
        avg_commission = trends.get("average_commission_value", 0)
        if avg_commission < 5:
            insights.append(
                f"Your average commission (${avg_commission:.2f}) is relatively low. "
                "Look for higher-ticket products with better commission rates."
            )
        elif avg_commission > 20:
            insights.append(
                f"Your average commission of ${avg_commission:.2f} is strong! "
                "Focus on promoting similar high-value products."
            )

        return insights

    def _get_historical_commissions(self) -> list[dict]:
        """Get historical commission data aggregated by month."""
        results = (
            self.db.execute(
                select(
                    func.strftime("%Y-%m", Commission.created_at).label("period"),
                    func.coalesce(func.sum(Commission.amount), 0).label("total"),
                    func.count(Commission.id).label("count"),
                )
                .group_by("period")
                .order_by("period")
            )
            .all()
        )

        return [
            {
                "period": r.period,
                "total": float(r.total),
                "count": r.count,
                "average": float(r.total) / r.count if r.count > 0 else 0,
            }
            for r in results
        ]
