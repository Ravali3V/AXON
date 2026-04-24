"""Centralized Amazon selector registry.

RULE: every CSS/XPath selector used against amazon.com lives in this file. When Amazon
rotates classnames (monthly), this is the ONE file that changes.

Convention: selectors are grouped by the page they target. Primary selector first,
fallbacks after. `first_match` in scrape modules tries them in order.

DO NOT add inline selectors elsewhere in the codebase. They will be rejected in review.
"""

from __future__ import annotations


# ============================================================================
# Search results page  —  /s?k=<brand>
# ============================================================================
SEARCH = {
    # Container for each result card — broadest possible match.
    # Dedup happens in asin_discovery via a `seen` set, so overlapping selectors
    # are safe. We need to catch: search results, sponsored, video modules,
    # brand-banner featured products — all the ASINs Amazon shows for the query.
    "result_card": [
        'div[data-asin]:not([data-asin=""])',
        'li[data-asin]:not([data-asin=""])',
    ],
    "asin_attr": "data-asin",
    # Brand byline inside a search result card — used to verify ASIN belongs to target brand
    "card_brand_byline": [
        'span.a-size-base-plus.a-color-base',
        '.s-line-clamp-1 span.a-color-secondary',
        'h2 a.a-link-normal span',
    ],
    # Total results text (e.g. "1-48 of over 1,000 results")
    "result_count": ["div.a-section.a-spacing-small.a-spacing-top-small span"],
    # Next-page link in pagination — try multiple selector strategies as Amazon rotates markup.
    "pagination_next": [
        'a.s-pagination-next:not(.s-pagination-disabled)',
        'a.s-pagination-button-next:not([aria-disabled="true"])',
        'li.a-last:not(.a-disabled) a',
        'li.a-last a',
        'a[aria-label="Go to next page"]',
        'a[aria-label*="next page"]',
        'span.s-pagination-next a',
    ],
    # Brand facet (sidebar "Brands" filter). Amazon uses p_89 as the brand refinement key.
    "brand_facet": [
        'a[href*="rh=p_89"]',
        'a[href*="&rh=p_89"]',
        'a[href*="p_89%3A"]',
        '#brandsRefinements li a',
        '#filters-p_lbr_brands_browse-bin a',
        'li[id^="p_89"] a',
        'div[data-component-id*="brands"] li a',
    ],
    # Brand store banner — the top-of-search "Shop X Store >" highlight that appears
    # when Amazon recognises the query as a brand.  Prefer banner-specific anchors
    # over generic /stores/ links (which may be per-ASIN "Visit the X Store" bylines).
    "store_link": [
        '.s-brand-banner a[href*="/stores/"]',
        'div[cel_widget_id*="brand"] a[href*="/stores/"]',
        'div[data-component-type*="brand"] a[href*="/stores/"]',
        '.s-brand-image-link',
        'a.s-brand-image-link',
        '#brandRow a[href*="/stores/"]',
        'h2 a[href*="/stores/"]',
        'a[href*="/stores/"]',
    ],
}


# ============================================================================
# Product Detail Page  —  /dp/<ASIN>
# ============================================================================
PDP = {
    "title": ["#productTitle", "span#productTitle"],
    "byline_store_link": [
        "a#bylineInfo",       # "Visit the X Store" anchor — has href directly
        "#bylineInfo a",      # anchor nested inside bylineInfo span/div
        "a[href*='/stores/']#bylineInfo",
        "#bylineInfo",        # fallback — span, href will be None but avoids crash
    ],
    "price": [
        "span.a-price:not(.a-text-price) span.a-offscreen",
        "#corePriceDisplay_desktop_feature_div span.a-offscreen",
        "#priceblock_ourprice",
        "#priceblock_saleprice",
    ],
    "bullets": [
        "#feature-bullets ul li span.a-list-item",
        "#feature-bullets ul li",
    ],
    "description": [
        "#productDescription",
        "#productDescription_feature_div",
    ],
    "images": [
        "#altImages li.imageThumbnail img",
        "#altImages li img",
    ],
    "main_image": ["#landingImage", "#imgBlkFront"],
    # A+ / Enhanced Brand Content
    "aplus": [
        "#aplus",
        "#aplus_feature_div",
    ],
    "aplus_modules": [
        "#aplus div.celwidget",
        "#aplus div.aplus-module",
    ],
    # Brand Story carousel (distinct from A+)
    "brand_story": [
        "#aplusBrandStory",
        "div.apm-brand-story-carousel",
    ],
    # Video module on PDP
    "video": [
        "#altImages li.videoThumbnail",
        'div[data-action="vse-videos"]',
        "#cr-video-showcase-video",
    ],
    # BSR in the product details section
    "bsr_rows": [
        "#productDetails_detailBullets_sections1 tr",
        "#detailBulletsWrapper_feature_div ul li",
        "#prodDetails tr",
    ],
    "bsr_text_match": "Best Sellers Rank",
    # Rating — Amazon uses several layouts; try all
    "rating_value": [
        "#acrPopover span.a-icon-alt",
        "span[data-hook='rating-out-of-text']",
        "#averageCustomerReviews span.a-icon-alt",
        "i[data-hook='average-star-rating'] span.a-icon-alt",
        "span.reviewCountTextLinkedHistogram span.a-icon-alt",
        "span.a-icon-alt",
    ],
    # Review count — try multiple placements
    "review_count_link": [
        "#acrCustomerReviewText",
        "span[data-hook='total-review-count']",
        "#acrCustomerReviewLink span",
        "#ratings-count-to-SRO",
        "a#acrCustomerReviewLink span",
    ],
    # Buy Box seller — Amazon rotates these frequently
    "buybox_seller": [
        "#merchantInfo",
        "#sellerProfileTriggerId",
        "#tabular-buybox div.tabular-buybox-container a",
        "#tabular-buybox-container a.a-link-normal",
        "#mbc-sold-by-link",
        "div#merchantInfoFeature_feature_div a",
        "#soldByThirdParty a",
        "span#sellerProfileTriggerId",
        "#newAccordionRow div.a-box-inner span#sellerProfileTriggerId",
    ],
    # Variations
    "variation_parent": [
        "#twister",
        "#variation_color_name",
    ],
    "variation_options": [
        "#variation_color_name li",
        "#variation_size_name li",
        "#variation_style_name li",
    ],
    # Robot/CAPTCHA check page signature
    "captcha_signal": [
        'form[action*="/errors/validateCaptcha"]',
        "div.a-box.a-alert-container",
    ],
}


# ============================================================================
# Brand Store  —  /stores/<brand>/page/<uuid>
# ============================================================================
BRAND_STORE = {
    "root": ["#storesRoot", "#storeContainer"],
    "page_count": ['div[data-testid="storefront-pages"] a'],
    "hero": [
        'div[data-testid="hero"]',
        "div.stores-widget-btf-hero",
    ],
    "videos": [
        'video[src]',
        'div[data-testid="video"]',
    ],
    "product_tiles": [
        'div[data-testid="storefront-asin-tile"]',
        "div.ProductGrid__tile",
    ],
    "navigation_items": [
        'nav[data-testid="navigation"] li',
        "div.stores-widget-navigation li",
    ],
}


# ============================================================================
# Review pages  —  /product-reviews/<ASIN>?pageNumber=N
# ============================================================================
REVIEW = {
    "review_card": [
        'div[data-hook="review"]',
        "div.review.aok-relative",
    ],
    "review_id_attr": "id",
    "review_title": [
        '[data-hook="review-title"]',
        "a.review-title",
    ],
    "review_body": [
        '[data-hook="review-body"] span',
        '[data-hook="review-body"]',
    ],
    "review_stars": [
        'i[data-hook="review-star-rating"] span.a-icon-alt',
        'i[data-hook="cmps-review-star-rating"] span.a-icon-alt',
    ],
    "verified_badge": ['[data-hook="avp-badge"]'],
    "helpful_votes": ['[data-hook="helpful-vote-statement"]'],
    "pagination_next": [
        'li.a-last a',
        "ul.a-pagination li.a-last a",
        'a[data-hook="pagination-bar-next"]',
        'span.a-pagination li.a-last a',
        'a[href*="pageNumber"]',
    ],
}
