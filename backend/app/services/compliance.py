"""Compliance Enforcement Engine

Enforces FTC disclosure requirements, platform-specific rules,
blocks non-compliant actions, and monitors platform policies.
"""
import re
from datetime import datetime
from typing import List, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import (
    ComplianceCheck,
    ComplianceRule,
    ContentDraft,
    Notification,
    PlatformPolicy,
    Product,
)
from ..config import get_settings


class ComplianceEngine:
    """Core compliance enforcement engine."""

    # FTC mandatory disclosure phrases
    FTC_DISCLOSURES = [
        "#ad",
        "#affiliate",
        "#commissionearned",
        "#sponsored",
        "affiliate link",
        "affiliate disclosure",
        "i may earn a commission",
        "this post contains affiliate links",
        "as an amazon associate i earn from qualifying purchases",
    ]

    # Keywords that indicate misleading claims
    MISLEADING_PATTERNS = [
        r"get rich quick",
        r"make \$[0-9,]+ (per|a|every) (day|week|month|hour)",
        r"earn \$[0-9,]+ (per|a|every) (day|week|month|hour)",
        r"guaranteed (income|earnings|returns|profits)",
        r"no (risk|money down|investment required)",
        r"100% (guaranteed|satisfaction|money back)",
        r"overnight (wealth|success|riches)",
        r"passive income with (no|zero) work",
        r"secret (method|system|formula|trick)",
        r"double your money",
        r"instant (wealth|results|profits)",
    ]

    # Cookie stuffing patterns
    COOKIE_STUFFING_PATTERNS = [
        r"<img[^>]+src=[\"']https?://[^\"']+ref=[^\"']+[\"'][^>]*/?>",
        r"<iframe[^>]+src=[\"']https?://[^\"']+ref=[^\"']+[\"']",
        r"document\.write\([\"']<script[^>]+src=[\"']https?://[^\"']+ref=[^\"']+",
        r"new\s+Image\(\)\.src\s*=\s*[\"']https?://[^\"']+ref=[^\"']+",
    ]

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def check_content_compliance(
        self, content_type: str, platform: str, content_text: str
    ) -> Tuple[bool, List[dict]]:
        """Run all compliance checks on content. Returns (passed, list_of_issues)."""
        checks = []
        passed_all = True

        # 1. Check for FTC disclosure
        if not self._has_ftc_disclosure(content_text):
            checks.append({
                "rule": "FTC Disclosure",
                "rule_type": "disclosure",
                "passed": False,
                "reason": "Content is missing mandatory FTC affiliate disclosure."
            })
            passed_all = False
        else:
            checks.append({
                "rule": "FTC Disclosure",
                "rule_type": "disclosure",
                "passed": True,
                "reason": None
            })

        # 2. Check for misleading claims
        misleading_issues = self._check_misleading_claims(content_text)
        checks.extend(misleading_issues)
        if any(not c["passed"] for c in misleading_issues):
            passed_all = False

        # 3. Check for spam patterns
        spam_issues = self._check_spam(content_text)
        checks.extend(spam_issues)
        if any(not c["passed"] for c in spam_issues):
            passed_all = False

        # 4. Check platform-specific rules
        platform_issues = self._check_platform_rules(platform, content_text)
        checks.extend(platform_issues)
        if any(not c["passed"] for c in platform_issues):
            passed_all = False

        # 5. Check for cookie stuffing
        if self._has_cookie_stuffing(content_text):
            checks.append({
                "rule": "Cookie Stuffing Prevention",
                "rule_type": "spam",
                "passed": False,
                "reason": "Content contains cookie stuffing techniques."
            })
            passed_all = False

        # 6. Check database compliance rules
        db_rule_issues = self._check_db_rules(platform, content_text)
        checks.extend(db_rule_issues)
        if any(not c["passed"] for c in db_rule_issues):
            passed_all = False

        # Log the compliance check
        log_entry = ComplianceCheck(
            content_type=content_type,
            content_text=content_text[:500],
            platform=platform,
            passed=passed_all,
            reason=(
                None
                if passed_all
                else "; ".join(
                    c["reason"] for c in checks if not c["passed"] and c["reason"]
                )[:500]
            ),
        )
        self.db.add(log_entry)

        # Create notification if compliance strict mode and failed
        if not passed_all and self.settings.compliance_strict_mode:
            notification = Notification(
                notification_type="compliance_alert",
                title="Compliance Check Failed",
                message=f"Content for {platform} ({content_type}) failed compliance checks: {log_entry.reason}",
                severity="warning",
            )
            self.db.add(notification)

        self.db.commit()
        return passed_all, checks

    def _has_ftc_disclosure(self, text: str) -> bool:
        """Check if text contains FTC-required affiliate disclosure."""
        text_lower = text.lower()
        for disclosure in self.FTC_DISCLOSURES:
            if disclosure in text_lower:
                return True
        return False

    def _check_misleading_claims(self, text: str) -> List[dict]:
        """Check for misleading or false claims."""
        results = []
        for pattern in self.MISLEADING_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                results.append({
                    "rule": "Misleading Claims Detection",
                    "rule_type": "claim",
                    "passed": False,
                    "reason": f"Potentially misleading claim detected: '{pattern}'"
                })
        return results

    def _check_spam(self, text: str) -> List[dict]:
        """Check for spam patterns."""
        issues = []
        # Check for excessive capitalization
        caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
        if caps_ratio > 0.5 and len(text) > 50:
            issues.append({
                "rule": "Spam Detection",
                "rule_type": "spam",
                "passed": False,
                "reason": "Excessive capitalization detected (>50% uppercase)."
            })
        # Check for excessive exclamation marks
        if text.count("!") > 5:
            issues.append({
                "rule": "Spam Detection",
                "rule_type": "spam",
                "passed": False,
                "reason": "Excessive exclamation marks detected."
            })
        # Check for excessive emoji usage
        emoji_pattern = re.compile(
            "[\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+", re.UNICODE
        )
        emojis = emoji_pattern.findall(text)
        if len(emojis) > 3:
            issues.append({
                "rule": "Spam Detection",
                "rule_type": "spam",
                "passed": False,
                "reason": "Excessive emoji usage detected."
            })
        return issues

    def _check_platform_rules(self, platform: str, text: str) -> List[dict]:
        """Check platform-specific rules."""
        issues = []
        text_lower = text.lower()

        if platform == "amazon" or platform == "twitter":
            # Amazon Associates: no coupon/deal sites, no bidding on trademarked terms
            if "amazon" in platform:
                if re.search(r"coupon|discount code|promo code|free shipping", text_lower):
                    issues.append({
                        "rule": "Amazon Associates Policy",
                        "rule_type": "policy",
                        "passed": False,
                        "reason": "Amazon Associates prohibits promoting coupons/deals as primary content."
                    })
            # Twitter: must use #ad disclosure in first 140 chars
            if platform == "twitter":
                if not any(d in text_lower[:140] for d in ["#ad", "#affiliate", "#sponsored"]):
                    issues.append({
                        "rule": "Twitter Ad Policy",
                        "rule_type": "policy",
                        "passed": False,
                        "reason": "Twitter requires #ad or #sponsored disclosure within first 140 characters."
                    })

        if platform == "facebook" or platform == "linkedin":
            if not any(d in text_lower for d in ["#ad", "#sponsored", "affiliate disclosure"]):
                issues.append({
                    "rule": f"{platform.title()} Ad Policy",
                    "rule_type": "policy",
                    "passed": False,
                    "reason": f"{platform.title()} requires clear affiliate/sponsored disclosure."
                })

        # ClickBank: no false income claims
        if "clickbank" in platform:
            if re.search(r"make \$[0-9,]+ (a|per) day|guaranteed income|passive income with no work", text_lower):
                issues.append({
                    "rule": "ClickBank Policy",
                    "rule_type": "policy",
                    "passed": False,
                    "reason": "ClickBank prohibits false income claims."
                })

        # ShareASale: no spam, no false claims
        if "sharesale" in platform:
            if re.search(r"get rich|overnight|no effort|guaranteed income|100%", text_lower):
                issues.append({
                    "rule": "ShareASale Policy",
                    "rule_type": "policy",
                    "passed": False,
                    "reason": "ShareASale prohibits misleading claims."
                })

        return issues

    def _check_db_rules(self, platform: str, text: str) -> List[dict]:
        """Check against custom compliance rules stored in database."""
        issues = []
        rules = self.db.scalars(
            select(ComplianceRule).where(
                ComplianceRule.platform == platform,
                ComplianceRule.enabled == True,
            )
        ).all()

        for rule in rules:
            if re.search(rule.pattern, text, re.IGNORECASE):
                issues.append({
                    "rule": rule.rule_name,
                    "rule_type": rule.rule_type,
                    "passed": False,
                    "reason": f"Matched compliance rule '{rule.rule_name}': {rule.description}"
                })
        return issues

    def _has_cookie_stuffing(self, text: str) -> bool:
        """Check for cookie stuffing techniques."""
        for pattern in self.COOKIE_STUFFING_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def auto_tag_disclosure(self, content_text: str, platform: str) -> str:
        """Automatically add FTC disclosure to content if missing."""
        if self._has_ftc_disclosure(content_text):
            return content_text

        disclosure_map = {
            "twitter": "\n\n#ad #affiliate",
            "linkedin": "\n\n*Affiliate Disclosure: This post contains affiliate links. I may earn a commission if you make a purchase.*",
            "wordpress": "\n\n<p><em>Affiliate Disclosure: This post contains affiliate links. As an Amazon Associate, I earn from qualifying purchases.</em></p>",
            "medium": "\n\n*Affiliate Disclosure: This story contains affiliate links. I may earn a commission if you click through and make a purchase.*",
            "blog": "\n\n*Affiliate Disclosure: This content includes affiliate links. I may earn a commission at no extra cost to you.*",
            "newsletter": "\n\n*Affiliate Disclosure: Some links in this newsletter are affiliate links. I may earn a commission if you purchase through them.*",
        }

        disclosure = disclosure_map.get(platform, "\n\n#ad #affiliatelink")
        return content_text + disclosure

    def add_platform_policy(self, platform: str, policy_text: str, policy_url: str | None = None) -> PlatformPolicy:
        """Add a new platform policy to track."""
        policy = PlatformPolicy(
            platform=platform,
            policy_text=policy_text,
            policy_url=policy_url,
            effective_date=datetime.utcnow(),
        )
        self.db.add(policy)
        self.db.commit()
        self.db.refresh(policy)
        return policy

    def check_policy_updates(self) -> List[dict]:
        """Check if platform policies need review (placeholder for future API monitoring)."""
        # In production, this would check RSS feeds/APIs for policy changes
        policies = self.db.scalars(select(PlatformPolicy)).all()
        stale_policies = []
        for policy in policies:
            if policy.last_checked_at:
                days_since_check = (datetime.utcnow() - policy.last_checked_at).days
                if days_since_check > 30:
                    stale_policies.append({
                        "platform": policy.platform,
                        "policy_id": policy.id,
                        "days_since_last_check": days_since_check
                    })
        return stale_policies

    def get_compliance_health_score(self) -> dict:
        """Calculate overall compliance health score."""
        total_checks = self.db.scalar(
            select(func.count(ComplianceCheck.id))
        ) or 0
        failed_checks = self.db.scalar(
            select(func.count(ComplianceCheck.id)).where(ComplianceCheck.passed == False)
        ) or 0
        total_rules = self.db.scalar(
            select(func.count(ComplianceRule.id))
        ) or 0
        active_rules = self.db.scalar(
            select(func.count(ComplianceRule.id)).where(ComplianceRule.enabled == True)
        ) or 0

        if total_checks == 0:
            pass_rate = 100.0
        else:
            pass_rate = round(((total_checks - failed_checks) / total_checks) * 100, 1)

        return {
            "health_score": pass_rate,
            "total_compliance_checks": total_checks,
            "failed_checks": failed_checks,
            "pass_rate_percent": pass_rate,
            "total_rules": total_rules,
            "active_rules": active_rules,
            "strict_mode": self.settings.compliance_strict_mode,
            "status": "healthy" if pass_rate >= 90 else ("warning" if pass_rate >= 70 else "critical"),
        }
