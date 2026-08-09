"""Content Distribution System

Generates compliant promotional content, embeds affiliate links,
schedules and publishes across multiple platforms via APIs.
"""
import re
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AffiliateLink, ContentDraft, Product
from ..config import get_settings
from .audit_logger import AuditLogger


class ContentGenerator:
    """Generates and manages promotional content with embedded affiliate links."""

    # Blog post templates by category
    BLOG_TEMPLATES = {
        "tech": {
            "title": "Top {year} {product_category} Picks: Expert Reviews & Buying Guide",
            "body": (
                "Are you looking for the best {product_category} in {year}? "
                "We've done the research so you don't have to. Here are our top picks:\n\n"
                "## Why Trust Our Recommendations?\n"
                "Our team spends hours researching and testing products so you can make informed decisions. "
                "We only recommend products that we believe offer genuine value.\n\n"
                "## Top Pick: {product_name}\n"
                "The {product_name} stands out for its exceptional quality and value. "
                "At just ${price}, it offers features that rival more expensive alternatives. "
                "With a {commission_rate}% commission rate, it's also a great option for affiliates.\n\n"
                "### Key Features:\n"
                "- Premium quality and durability\n"
                "- Excellent value for money\n"
                "- Positive customer reviews\n\n"
                "### Pros and Cons\n"
                "**Pros:**\n"
                "- High-quality build\n"
                "- Affordable price point\n"
                "- Great customer support\n\n"
                "**Cons:**\n"
                "- Limited color options\n"
                "- May not suit all needs\n\n"
                "## What to Look For in {product_category}\n"
                "When shopping for {product_category}, consider these factors:\n"
                "1. Quality and durability\n"
                "2. Price and value\n"
                "3. Customer reviews\n"
                "4. Warranty and support\n\n"
                "## Final Verdict\n"
                "The {product_name} is our top recommendation for {year}. "
                "Click below to check the current price and availability.\n\n"
                "{{AFFILIATE_LINK}}\n\n"
                "*Affiliate Disclosure: This post contains affiliate links. "
                "We may earn a commission if you make a purchase through these links at no extra cost to you.*"
            ),
        },
        "fitness": {
            "title": "Transform Your Body in {year}: The Ultimate {product_name} Review",
            "body": (
                "Are you ready to transform your fitness journey? "
                "In this comprehensive review, we explore the {product_name} and how it can help you achieve your goals.\n\n"
                "## Why {product_name}?\n"
                "With thousands of satisfied users, {product_name} has proven to be an effective solution for fitness enthusiasts. "
                "Priced at just ${price}, it's an investment in your health.\n\n"
                "## What You'll Learn\n"
                "- How {product_name} works\n"
                "- Key benefits and features\n"
                "- Real user results\n"
                "- Whether it's right for you\n\n"
                "## Key Benefits\n"
                "1. Scientifically-backed approach\n"
                "2. Easy to follow program\n"
                "3. Results in weeks, not months\n"
                "4. Supportive community\n\n"
                "## Who Is This For?\n"
                "This program is ideal for:\n"
                "- Beginners looking to start their fitness journey\n"
                "- Intermediate enthusiasts wanting to break plateaus\n"
                "- Anyone seeking a structured approach to health\n\n"
                "## Get Started Today\n"
                "Ready to transform your life? Click the link below to get started with {product_name}.\n\n"
                "{{AFFILIATE_LINK}}\n\n"
                "*Affiliate Disclosure: This review contains affiliate links. "
                "I may earn a commission if you purchase through these links at no additional cost to you.*"
            ),
        },
        "finance": {
            "title": "{product_name} Review {year}: Is It Worth Your Money?",
            "body": (
                "In today's digital age, finding the right financial tool can be overwhelming. "
                "That's why we've thoroughly tested {product_name} to bring you this honest review.\n\n"
                "## What Is {product_name}?\n"
                "{product_name} is a comprehensive financial solution designed to help you "
                "achieve your financial goals. At ${price}, it offers incredible value.\n\n"
                "## How We Tested\n"
                "Our team spent {weeks} weeks evaluating {product_name} based on:\n"
                "- Ease of use\n"
                "- Features and functionality\n"
                "- Customer support\n"
                "- Value for money\n\n"
                "## Our Rating\n"
                "⭐⭐⭐⭐⭐ (4.5/5)\n\n"
                "## What We Loved\n"
                "- User-friendly interface\n"
                "- Comprehensive features\n"
                "- Excellent support\n"
                "- Great value\n\n"
                "## What Could Be Better\n"
                "- Learning curve for advanced features\n"
                "- Limited integrations\n\n"
                "## Should You Buy It?\n"
                "If you're serious about your financial future, {product_name} is a solid investment. "
                "Click below to learn more.\n\n"
                "{{AFFILIATE_LINK}}\n\n"
                "*Affiliate Disclosure: This post includes affiliate links. "
                "We may earn a commission at no extra cost to you. All opinions are our own.*"
            ),
        },
        "default": {
            "title": "Why {product_name} Is Trending in {year}: Complete Review",
            "body": (
                "Looking for honest information about {product_name}? "
                "You've come to the right place. In this comprehensive guide, "
                "we cover everything you need to know.\n\n"
                "## What Is {product_name}?\n"
                "{product_name} has been gaining popularity for good reason. "
                "With a price of ${price}, it offers excellent value for what it provides.\n\n"
                "## Key Features\n"
                "- High-quality product\n"
                "- Competitive pricing at ${price}\n"
                "- Excellent commission rate of {commission_rate}%\n"
                "- Positive user feedback\n\n"
                "## How It Compares\n"
                "When compared to alternatives, {product_name} stands out for its:\n"
                "1. Superior quality\n"
                "2. Competitive pricing\n"
                "3. Strong customer satisfaction\n\n"
                "## Customer Reviews\n"
                "Users consistently praise {product_name} for its reliability and performance. "
                "Here's what some customers are saying:\n\n"
                "> \"This is the best investment I've made this year!\" - Sarah M.\n"
                "> \"Exceeded my expectations in every way.\" - James K.\n\n"
                "## Ready to Try It?\n"
                "Don't just take our word for it. Click the link below to see current pricing and availability.\n\n"
                "{{AFFILIATE_LINK}}\n\n"
                "*Affiliate Disclosure: This content includes affiliate links. "
                "I may earn a commission if you make a purchase through these links.*"
            ),
        },
    }

    # Social media templates
    SOCIAL_TEMPLATES = {
        "twitter": [
            "Check out {product_name}! It's amazing for {benefit}. Highly recommend! 🎯 {link} #ad #affiliate",
            "Just discovered {product_name} and I'm impressed! {benefit} for just ${price}. {link} #affiliate",
            "Need {benefit}? {product_name} has you covered. See why I love it: {link} #sponsored",
            "{product_name} is a game-changer for {benefit}. Don't miss out! {link} #ad #commissionearned",
            "I've been using {product_name} and the results speak for themselves. Check it out: {link} #affiliate",
        ],
        "linkedin": [
            "I recently came across {product_name} and wanted to share my thoughts. It's helping professionals like us with {benefit}. Check it out: {link}\n\n*Affiliate Disclosure: This post contains affiliate links. I may earn a commission.*",
            "In my search for {benefit}, I discovered {product_name}. It's been incredibly useful for my workflow. Worth a look: {link}\n\n#affiliate #professionaldevelopment",
            "Thoroughly impressed with {product_name} for {benefit}. If you're in the market for a solution, give it a try: {link}\n\n*Affiliate link included*",
        ],
        "newsletter": [
            "## Product Spotlight: {product_name}\n\nThis week we're highlighting {product_name}. Priced at just ${price}, it's perfect for {benefit}.\n\n{link}\n\n*Affiliate Disclosure: Some links in this newsletter are affiliate links.*",
            "## Recommended Resource: {product_name}\n\nLooking for {benefit}? We've found that {product_name} delivers exceptional value at ${price}.\n\n{link}\n\n*This is an affiliate link.*",
        ],
    }

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def generate_blog_post(self, product: Product, category: str = "default") -> dict:
        """Generate a blog post for a given product."""
        template = self.BLOG_TEMPLATES.get(category, self.BLOG_TEMPLATES["default"])
        year = datetime.utcnow().year

        # Determine category for title
        product_category = product.category or product.name

        # Build the body
        body = template["body"].format(
            product_name=product.name,
            price=product.price,
            commission_rate=int(product.commission_rate * 100),
            product_category=product_category,
            year=year,
            weeks="2-3",
        )

        title = template["title"].format(
            product_name=product.name,
            product_category=product_category,
            year=year,
        )

        return {"title": title, "body": body, "category": category}

    def generate_social_post(
        self, product: Product, platform: str, benefit: str = "improving productivity"
    ) -> str:
        """Generate a social media post for a given product."""
        templates = self.SOCIAL_TEMPLATES.get(platform, self.SOCIAL_TEMPLATES["twitter"])
        import random

        template = random.choice(templates)
        post = template.format(
            product_name=product.name,
            price=product.price,
            benefit=benefit,
            link="{{AFFILIATE_LINK}}",
        )
        return post

    def create_content_draft(
        self,
        title: str,
        content_type: str,
        platform: str,
        body: str,
        affiliate_link_id: int | None = None,
        scheduled_at: datetime | None = None,
    ) -> ContentDraft:
        """Create a content draft with optional scheduling."""
        draft = ContentDraft(
            title=title,
            content_type=content_type,
            platform=platform,
            body=body,
            affiliate_link_id=affiliate_link_id,
            status="draft",
            scheduled_at=scheduled_at,
        )
        self.db.add(draft)
        self.db.commit()
        self.db.refresh(draft)

        # ── Persistent audit logging ────────────────────────────────
        logger = AuditLogger(self.db)
        logger.log_content_generated(draft.id, content_type, platform, title)

        return draft

    def embed_affiliate_link(self, body: str, link_url: str) -> str:
        """Embed affiliate link into content body."""
        return body.replace("{{AFFILIATE_LINK}}", link_url)

    def publish_content(self, draft: ContentDraft) -> ContentDraft:
        """Publish content to the target platform (mock implementation with real API stubs)."""
        platform = draft.platform
        body = draft.body

        try:
            if platform == "twitter":
                external_id = self._post_to_twitter(body)
            elif platform == "linkedin":
                external_id = self._post_to_linkedin(body)
            elif platform == "wordpress":
                external_id = self._post_to_wordpress(draft.title, body)
            elif platform == "medium":
                external_id = self._post_to_medium(draft.title, body)
            else:
                raise ValueError(f"Unsupported platform: {platform}")

            draft.status = "published"
            draft.published_at = datetime.utcnow()
            draft.external_post_id = external_id
            draft.error_message = None
            self.db.commit()
            self.db.refresh(draft)

        except Exception as e:
            draft.status = "failed"
            draft.error_message = str(e)
            self.db.commit()
            self.db.refresh(draft)

        return draft

    def _post_to_twitter(self, content: str) -> str:
        """Post to Twitter/X API (stub - requires tweepy and API keys)."""
        settings = self.settings
        if settings.twitter_api_key and settings.twitter_api_secret:
            try:
                # In production, use tweepy:
                # import tweepy
                # auth = tweepy.OAuth1UserHandler(
                #     settings.twitter_api_key,
                #     settings.twitter_api_secret,
                #     settings.twitter_access_token,
                #     settings.twitter_access_secret,
                # )
                # api = tweepy.API(auth)
                # tweet = api.update_status(content[:280])
                # return str(tweet.id)
                pass
            except Exception as e:
                raise RuntimeError(f"Twitter API error: {e}")
        # Mock: return fake tweet ID
        return f"tw-{uuid.uuid4().hex[:12]}"

    def _post_to_linkedin(self, content: str) -> str:
        """Post to LinkedIn API (stub)."""
        settings = self.settings
        if settings.linkedin_access_token:
            try:
                # In production, use requests to LinkedIn API:
                # import requests
                # headers = {"Authorization": f"Bearer {settings.linkedin_access_token}"}
                # response = requests.post(
                #     "https://api.linkedin.com/v2/ugcPosts",
                #     json={"author": ..., "lifecycleState": "PUBLISHED", ...},
                #     headers=headers,
                # )
                pass
            except Exception as e:
                raise RuntimeError(f"LinkedIn API error: {e}")
        return f"li-{uuid.uuid4().hex[:12]}"

    def _post_to_wordpress(self, title: str, content: str) -> str:
        """Post to WordPress via XML-RPC (stub)."""
        settings = self.settings
        if settings.wordpress_url and settings.wordpress_username and settings.wordpress_password:
            try:
                # In production, use python-wordpress-xmlrpc:
                # from wordpress_xmlrpc import Client, WordPressPost
                # from wordpress_xmlrpc.methods.posts import NewPost
                # client = Client(settings.wordpress_url + "/xmlrpc.php",
                #                 settings.wordpress_username,
                #                 settings.wordpress_password)
                # post = WordPressPost()
                # post.title = title
                # post.content = content
                # post.post_status = 'publish'
                # post_id = client.call(NewPost(post))
                # return str(post_id)
                pass
            except Exception as e:
                raise RuntimeError(f"WordPress API error: {e}")
        return f"wp-{uuid.uuid4().hex[:12]}"

    def _post_to_medium(self, title: str, content: str) -> str:
        """Post to Medium API (stub)."""
        # In production, use Medium API:
        # import requests
        # headers = {"Authorization": f"Bearer {settings.medium_token}"}
        # response = requests.post(
        #     "https://api.medium.com/v1/users/me/posts",
        #     json={"title": title, "contentFormat": "markdown", "content": content, ...},
        #     headers=headers,
        # )
        return f"md-{uuid.uuid4().hex[:12]}"

    def get_pending_content(self) -> List[ContentDraft]:
        """Get all pending/scheduled content."""
        return list(
            self.db.scalars(
                select(ContentDraft).where(
                    ContentDraft.status.in_(["draft", "scheduled"])
                ).order_by(ContentDraft.created_at.desc())
            ).all()
        )

    def get_published_content(self) -> List[ContentDraft]:
        """Get all published content."""
        return list(
            self.db.scalars(
                select(ContentDraft).where(
                    ContentDraft.status == "published"
                ).order_by(ContentDraft.published_at.desc())
            ).all()
        )

