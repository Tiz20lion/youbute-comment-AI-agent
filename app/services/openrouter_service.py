"""
OpenRouter API Service

This service handles all interactions with the OpenRouter API for:
- AI model integration
- Content analysis functions
- Comment generation
- Error handling and retry logic
- Rate limiting
"""

import asyncio
import json
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta
import httpx
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from ..config import settings
from ..utils.logging_config import get_logger
from ..models.schemas import VideoData, CommentData

logger = get_logger(__name__)


class OpenRouterService:
    """OpenRouter API service for AI content analysis and generation."""
    
    def __init__(self):
        """Initialize OpenRouter service with API client."""
        self.client = AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_BASE_URL,
            timeout=httpx.Timeout(float(settings.ANALYSIS_TIMEOUT))
        )
        self.rate_limiter = AsyncRateLimiter(
            max_requests_per_minute=settings.OPENROUTER_REQUESTS_PER_MINUTE
        )
        
    async def __aenter__(self):
        """Async context manager entry."""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.close()

    async def analyze_video_content(
        self, 
        video: VideoData, 
        transcript: Optional[str] = None,
        comments: List[CommentData] = None
    ) -> Dict[str, Any]:
        """
        Analyze video content using AI with enhanced prompting strategies.
        
        Args:
            video: VideoData object
            transcript: Video transcript text
            comments: List of comment data
            
        Returns:
            Comprehensive content analysis
        """
        try:
            await self.rate_limiter.acquire()
            
            # Prepare comprehensive content for analysis
            content_parts = [f"Title: {video.title}"]
            
            if video.description:
                content_parts.append(f"Description: {video.description[:1000]}")
            
            if transcript:
                content_parts.append(f"Transcript: {transcript[:2000]}")
            
            if comments:
                top_comments = [c.text[:200] for c in comments[:10] if c.text]
                if top_comments:
                    content_parts.append(f"Top Comments: {' | '.join(top_comments)}")
            
            content = "\n\n".join(content_parts)
            
            prompt = f"""You are a senior digital content strategist and audience psychology expert with deep expertise in YouTube ecosystem analysis. Your role is to provide comprehensive, actionable insights that drive content strategy and audience engagement.

CONTENT ANALYSIS TARGET:
{content}

VIDEO METRICS CONTEXT:
- Channel: {video.channel_title}
- Views: {video.view_count:,}
- Likes: {video.like_count:,}
- Comments: {video.comment_count:,}

STRATEGIC ANALYSIS FRAMEWORK:
Analyze this content through multiple strategic lenses:

1. CONTENT STRATEGY ANALYSIS:
   - Core value proposition and unique angle
   - Content positioning within niche/category
   - Competitive differentiation factors
   - Scalability and series potential

2. AUDIENCE PSYCHOLOGY ASSESSMENT:
   - Primary audience motivations and pain points
   - Emotional engagement drivers
   - Knowledge level and learning preferences
   - Community building potential

3. ENGAGEMENT OPTIMIZATION INSIGHTS:
   - Hook effectiveness and retention factors
   - Discussion catalyst elements
   - Shareability and viral potential
   - Call-to-action opportunities

4. CONTENT QUALITY EVALUATION:
   - Information density and value delivery
   - Production quality and presentation
   - Authenticity and credibility indicators
   - Educational or entertainment balance

REQUIRED OUTPUT (JSON format):
{{
    "strategic_analysis": {{
        "content_positioning": "How this content fits in the market landscape",
        "unique_value_proposition": "What makes this content distinctly valuable",
        "competitive_advantages": ["advantage1", "advantage2"],
        "scalability_assessment": "Potential for series/follow-up content"
    }},
    "audience_insights": {{
        "primary_demographics": "Target audience description",
        "psychological_drivers": ["motivation1", "motivation2"],
        "engagement_preferences": "How this audience likes to interact",
        "knowledge_level": "beginner/intermediate/advanced",
        "community_potential": "Likelihood of building engaged community"
    }},
    "content_optimization": {{
        "engagement_hooks": ["Specific elements that capture attention"],
        "retention_factors": ["Elements that keep viewers watching"],
        "discussion_catalysts": ["Aspects that encourage comments"],
        "shareability_factors": ["What makes this shareable"],
        "improvement_opportunities": ["Specific enhancement suggestions"]
    }},
    "themes": ["Primary theme 1", "Primary theme 2", "Primary theme 3"],
    "summary": "2-3 sentence strategic summary of content value and positioning",
    "engagement_insights": "Analysis of audience interaction patterns and quality",
    "tone": "Overall communication style and brand personality",
    "key_takeaways": ["Actionable insight 1", "Actionable insight 2"],
    "discussion_points": ["Discussion starter 1", "Discussion starter 2", "Discussion starter 3"],
    "content_score": 8.5,
    "strategic_recommendations": ["Strategic recommendation 1", "Strategic recommendation 2"]
}}

ANALYSIS QUALITY STANDARDS:
✅ Provide insights that are:
- Strategically actionable for content creators
- Psychologically informed about audience behavior
- Competitively aware of market positioning
- Specific and evidence-based

❌ Avoid analyses that are:
- Generic or template-based
- Disconnected from actual content evidence
- Overly academic without practical application
- Biased toward any particular content style

Focus on delivering strategic intelligence that helps creators understand their content's market position, audience appeal, and optimization opportunities."""
            
            response = await self._make_completion_request(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=settings.CONTENT_ANALYZER_MAX_TOKENS,
                temperature=settings.CONTENT_ANALYZER_TEMPERATURE,
                model=settings.get_content_analyzer_model()
            )
            
            if response and response.choices:
                analysis_text = response.choices[0].message.content.strip()
                try:
                    analysis_data = json.loads(analysis_text)
                    logger.info(f"Content analysis completed for: {video.title}")
                    return analysis_data
                except json.JSONDecodeError:
                    # Fallback to structured text analysis
                    logger.warning("Failed to parse JSON response, using text analysis")
                    return self._parse_text_analysis(analysis_text, video)
            
            return {"error": "Failed to generate analysis"}
            
        except Exception as e:
            logger.error(f"Error analyzing video content: {str(e)}")
            return {"error": f"Analysis failed: {str(e)}"}

    async def generate_engaging_comment(
        self,
        video: VideoData,
        analysis: Dict[str, Any],
        style: str = "engaging"
    ) -> Dict[str, Any]:
        """
        Generate an engaging comment with advanced psychology and engagement strategies.
        
        Args:
            video: VideoData object
            analysis: Content analysis results
            style: Comment style preference
            
        Returns:
            Dictionary with generated comment and metadata
        """
        try:
            await self.rate_limiter.acquire()
            
            # Prepare strategic context for comment generation
            themes_text = ", ".join(analysis.get("themes", []))
            summary = analysis.get("summary", "")
            discussion_points = analysis.get("discussion_points", [])
            audience_insights = analysis.get("audience_insights", {})
            engagement_hooks = analysis.get("content_optimization", {}).get("engagement_hooks", [])
            
            # Enhanced style definitions with psychological backing
            style_strategies = {
                "engaging": {
                    "approach": "Create curiosity and encourage discussion through questions and insights",
                    "psychology": "Leverage social proof and community building",
                    "tone": "Enthusiastic but authentic, conversational and inclusive"
                },
                "thoughtful": {
                    "approach": "Provide analytical depth and meaningful observations",
                    "psychology": "Appeal to intellectual curiosity and expertise recognition",
                    "tone": "Reflective and insightful, demonstrating careful consideration"
                },
                "casual": {
                    "approach": "Sound like a friend sharing genuine reactions and thoughts",
                    "psychology": "Build relatability and social connection",
                    "tone": "Natural and relaxed, using everyday language and expressions"
                },
                "professional": {
                    "approach": "Demonstrate expertise while adding constructive value",
                    "psychology": "Establish credibility and thought leadership",
                    "tone": "Knowledgeable and authoritative yet approachable"
                }
            }
            
            style_config = style_strategies.get(style, style_strategies["engaging"])
            
            prompt = f"""You are a master of digital communication and audience engagement psychology. Your expertise lies in crafting comments that create genuine connections, spark meaningful discussions, and add authentic value to online communities.

STRATEGIC CONTEXT:
Video: "{video.title}"
Channel: {video.channel_title}
Performance: {video.view_count:,} views, {video.like_count:,} likes, {video.comment_count:,} comments

CONTENT INTELLIGENCE:
Main Themes: {themes_text}
Content Summary: {summary}
Audience Profile: {audience_insights.get('primary_demographics', 'General audience')}
Engagement Hooks: {', '.join(engagement_hooks[:3])}
Discussion Opportunities: {', '.join(discussion_points[:3])}

COMMENT STRATEGY:
Style: {style.title()}
Approach: {style_config['approach']}
Psychology: {style_config['psychology']}
Tone: {style_config['tone']}

ENGAGEMENT PSYCHOLOGY PRINCIPLES:
✅ APPLY:
- Reciprocity: Acknowledge the creator's effort or expertise
- Social Proof: Reference community or shared experiences
- Curiosity Gap: Ask questions that others want answered
- Value Addition: Share insights or perspectives that enhance discussion
- Authenticity: Sound genuine and personally invested
- Specificity: Reference particular moments or concepts from the content

✅ OPTIMIZE FOR:
- Conversation Starters: Elements that encourage replies
- Community Building: Language that includes others
- Creator Appreciation: Recognition that feels genuine
- Knowledge Sharing: Insights that demonstrate engagement
- Question Catalysts: Thoughtful questions that drive discussion

❌ AVOID:
- Generic praise without substance
- Self-promotional content or links
- Controversial or divisive statements
- Overly long or complex responses
- Copying obvious observations
- Artificial or scripted language

COMMENT CRAFTING FRAMEWORK:
1. HOOK: Open with something that captures attention
2. VALUE: Add insight, question, or observation
3. CONNECTION: Link to broader themes or audience interests
4. CATALYST: Include element that encourages engagement

CHARACTER LIMITS: 50-200 characters optimal for engagement

Generate a single, strategically crafted comment that exemplifies authentic engagement and community building:"""
            
            response = await self._make_completion_request(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=settings.COMMENT_GENERATOR_MAX_TOKENS,
                temperature=settings.COMMENT_GENERATOR_TEMPERATURE,
                model=settings.get_comment_generator_model()
            )
            
            if response and response.choices:
                comment_text = response.choices[0].message.content.strip()
                
                # Enhanced comment cleaning and validation
                comment_text = self._clean_and_validate_comment(comment_text)
                
                # Analyze comment quality
                quality_metrics = self._analyze_comment_quality(comment_text, analysis)
                
                logger.info(f"Generated {style} comment for video: {video.title}")
                
                return {
                    "comment": comment_text,
                    "style": style,
                    "length": len(comment_text),
                    "model_used": settings.get_comment_generator_model(),
                    "themes_referenced": themes_text,
                    "quality_score": quality_metrics["overall_score"],
                    "engagement_potential": quality_metrics["engagement_potential"],
                    "authenticity_score": quality_metrics["authenticity_score"],
                    "generated_at": datetime.now().isoformat(),
                    "strategy_applied": style_config["approach"]
                }
            
            # Enhanced fallback with style awareness
            return self._generate_style_aware_fallback(video, analysis, style)
            
        except Exception as e:
            logger.error(f"Error generating comment: {str(e)}")
            return self._generate_style_aware_fallback(video, analysis, style, error=str(e))
    
    def _clean_and_validate_comment(self, comment: str) -> str:
        """Clean and validate generated comment with enhanced rules."""
        # Remove common AI artifacts
        comment = comment.strip().strip('"\'')
        
        # Remove AI-generated prefixes
        prefixes = [
            "Here's a comment:", "Comment:", "Generated comment:", 
            "My comment:", "I would comment:", "A good comment would be:",
            "Here's an engaging comment:", "Sample comment:"
        ]
        
        for prefix in prefixes:
            if comment.lower().startswith(prefix.lower()):
                comment = comment[len(prefix):].strip()
        
        # Ensure proper capitalization
        if comment and comment[0].islower():
            comment = comment[0].upper() + comment[1:]
        
        # Remove excessive punctuation
        comment = comment.replace("!!!", "!").replace("???", "?")
        
        return comment
    
    def _analyze_comment_quality(self, comment: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze the quality of a generated comment."""
        quality_metrics = {
            "overall_score": 7.0,
            "engagement_potential": "medium",
            "authenticity_score": 7.0,
            "specificity_score": 5.0,
            "question_included": False
        }
        
        # Check for questions (engagement driver)
        if "?" in comment:
            quality_metrics["question_included"] = True
            quality_metrics["engagement_potential"] = "high"
            quality_metrics["overall_score"] += 1.0
        
        # Check for specificity (references to content)
        themes = analysis.get("themes", [])
        for theme in themes:
            if theme.lower() in comment.lower():
                quality_metrics["specificity_score"] += 2.0
                quality_metrics["overall_score"] += 0.5
        
        # Check length (optimal range)
        length = len(comment)
        if 50 <= length <= 200:
            quality_metrics["overall_score"] += 0.5
        elif length < 30:
            quality_metrics["overall_score"] -= 1.0
        elif length > 300:
            quality_metrics["overall_score"] -= 0.5
        
        # Check for authenticity indicators
        authentic_indicators = ["I", "my", "really", "love", "think", "feel", "experience"]
        authenticity_count = sum(1 for indicator in authentic_indicators if indicator in comment.lower())
        quality_metrics["authenticity_score"] = min(10.0, 5.0 + authenticity_count * 0.5)
        
        # Normalize overall score
        quality_metrics["overall_score"] = min(10.0, max(1.0, quality_metrics["overall_score"]))
        
        return quality_metrics
    
    def _generate_style_aware_fallback(self, video: VideoData, analysis: Dict[str, Any], style: str, error: str = None) -> Dict[str, Any]:
        """Generate fallback comment with style awareness."""
        themes = analysis.get("themes", ["this topic"])
        
        fallback_templates = {
            "engaging": [
                f"This really opened my eyes to {themes[0] if themes else 'new perspectives'}! What's your take on this?",
                f"Love how you explained {themes[0] if themes else 'this concept'}! Got me thinking about my own experience.",
                f"Such valuable insights on {themes[0] if themes else 'this topic'}! Anyone else trying this approach?"
            ],
            "thoughtful": [
                f"Your analysis of {themes[0] if themes else 'this subject'} aligns with my observations in the field.",
                f"Appreciate the depth you brought to {themes[0] if themes else 'this topic'}. Well researched.",
                f"This adds valuable perspective to the {themes[0] if themes else 'ongoing'} discussion."
            ],
            "casual": [
                f"Dude, this stuff about {themes[0] if themes else 'this'} is so cool! Thanks for sharing.",
                f"Really enjoyed this! The {themes[0] if themes else 'part about'} was my favorite bit.",
                f"Great video! Always wondered about {themes[0] if themes else 'this stuff'}."
            ],
            "professional": [
                f"Excellent overview of {themes[0] if themes else 'the subject matter'}. Clear and informative.",
                f"Thank you for this comprehensive analysis of {themes[0] if themes else 'the topic'}.",
                f"Well-structured presentation on {themes[0] if themes else 'this important topic'}."
            ]
        }
        
        templates = fallback_templates.get(style, fallback_templates["engaging"])
        comment = templates[0]  # Use first template as fallback
        
        return {
            "comment": comment,
            "style": style,
            "length": len(comment),
            "model_used": "fallback",
            "themes_referenced": ", ".join(themes[:2]),
            "quality_score": 6.0,
            "engagement_potential": "medium",
            "authenticity_score": 7.0,
            "generated_at": datetime.now().isoformat(),
            "fallback_reason": error or "AI generation failed",
            "strategy_applied": f"Template-based {style} approach"
        }

    async def generate_video_suggestions(
        self,
        video: VideoData,
        analysis: Dict[str, Any],
        num_suggestions: int = 3
    ) -> List[str]:
        """
        Generate video content suggestions based on analysis.
        
        Args:
            video: VideoData object
            analysis: Content analysis results
            num_suggestions: Number of suggestions to generate
            
        Returns:
            List of video suggestions
        """
        try:
            await self.rate_limiter.acquire()
            
            themes = analysis.get("themes", [])
            discussion_points = analysis.get("discussion_points", [])
            
            prompt = f"""
            Based on this video analysis, suggest {num_suggestions} related video topics that would interest the same audience:

            Original Video: "{video.title}"
            Channel: {video.channel_title}
            Themes: {', '.join(themes)}
            Discussion Points: {', '.join(discussion_points[:3])}

            Generate {num_suggestions} specific, actionable video topic suggestions that:
            - Build on the themes from the original video
            - Would appeal to the same audience
            - Are specific enough to be actionable
            - Avoid being too similar to the original

            Format as a simple list, one suggestion per line.
            """
            
            response = await self._make_completion_request(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.8,
                model=settings.get_comment_generator_model()
            )
            
            suggestions_text = response.choices[0].message.content.strip()
            suggestions = [s.strip().lstrip('•-*1234567890. ') for s in suggestions_text.split('\n') if s.strip()]
            
            logger.info(f"Generated {len(suggestions)} video suggestions")
            return suggestions[:num_suggestions]
            
        except Exception as e:
            logger.error(f"Error generating video suggestions: {str(e)}")
            return [
                f"More content about {themes[0] if themes else 'this topic'}",
                f"Deep dive into {themes[1] if len(themes) > 1 else 'related concepts'}",
                f"Beginner's guide to {themes[0] if themes else 'the subject'}"
            ]

    async def generate_completion(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        temperature: float = 0.7,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate completion using OpenRouter API (public method for agents).
        
        Args:
            messages: List of message dictionaries
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            model: Model to use (defaults to settings.OPENROUTER_MODEL)
            
        Returns:
            Dictionary with success status and content
        """
        try:
            response = await self._make_completion_request(messages, max_tokens, temperature, model)
            return {
                "success": True,
                "content": response.choices[0].message.content,
                "model": response.model,
                "usage": response.usage.dict() if response.usage else None
            }
        except Exception as e:
            logger.error(f"Generate completion failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "content": None
            }

    async def _make_completion_request(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        temperature: float = 0.7,
        model: Optional[str] = None
    ) -> ChatCompletion:
        """
        Make a completion request to OpenRouter API.
        
        Args:
            messages: List of message dictionaries
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            model: Model to use (defaults to settings.OPENROUTER_MODEL)
            
        Returns:
            ChatCompletion response
        """
        if not model:
            model = settings.OPENROUTER_MODEL
            
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=float(settings.ANALYSIS_TIMEOUT)
            )
            
            logger.debug(f"OpenRouter API request successful with model: {model}")
            return response
            
        except Exception as e:
            logger.error(f"OpenRouter API request failed: {str(e)}")
            raise

    async def check_api_status(self) -> Dict[str, Any]:
        """
        Check OpenRouter API status and rate limits.
        
        Returns:
            Dictionary with API status information
        """
        try:
            # Simple test request
            response = await self._make_completion_request(
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=10,
                temperature=0.1
            )
            
            return {
                "status": "healthy",
                "model": settings.OPENROUTER_MODEL,
                "rate_limits": {
                    "requests_per_minute": await self.rate_limiter.get_remaining_requests_minute()
                },
                "test_response": response.choices[0].message.content
            }
            
        except Exception as e:
            logger.error(f"OpenRouter API health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "model": settings.OPENROUTER_MODEL
            }


class AsyncRateLimiter:
    """Async rate limiter for API requests."""
    
    def __init__(self, max_requests_per_minute: int):
        """Initialize rate limiter."""
        self.max_requests_per_minute = max_requests_per_minute
        self.requests_minute = []
        self._lock = asyncio.Lock()
        
    async def acquire(self):
        """Acquire rate limit permission."""
        async with self._lock:
            now = datetime.now()
            
            # Clean old requests (older than 1 minute)
            self.requests_minute = [
                req_time for req_time in self.requests_minute
                if now - req_time < timedelta(minutes=1)
            ]
            
            # Check if we can make a request
            if len(self.requests_minute) >= self.max_requests_per_minute:
                # Calculate wait time
                oldest_request = min(self.requests_minute)
                wait_time = 60 - (now - oldest_request).total_seconds()
                
                if wait_time > 0:
                    logger.info(f"Rate limit reached, waiting {wait_time:.1f} seconds")
                    await asyncio.sleep(wait_time)
                    
                    # Clean requests again after waiting
                    now = datetime.now()
                    self.requests_minute = [
                        req_time for req_time in self.requests_minute
                        if now - req_time < timedelta(minutes=1)
                    ]
            
            # Record this request
            self.requests_minute.append(now)

    async def get_remaining_requests_minute(self) -> int:
        """Get remaining requests for current minute."""
        now = datetime.now()
        self.requests_minute = [
            req_time for req_time in self.requests_minute
            if now - req_time < timedelta(minutes=1)
        ]
        return max(0, self.max_requests_per_minute - len(self.requests_minute))


# Service factory function
async def create_openrouter_service() -> OpenRouterService:
    """Create and return an OpenRouter service instance."""
    return OpenRouterService()


# Convenience functions for direct usage
async def analyze_video(
    video: VideoData,
    transcript: Optional[str] = None,
    comments: List[CommentData] = None
) -> Dict[str, Any]:
    """
    Analyze video content using OpenRouter service.
    
    Args:
        video: VideoData object
        transcript: Optional transcript
        comments: Optional comments list
        
    Returns:
        Analysis results dictionary
    """
    async with OpenRouterService() as service:
        return await service.analyze_video_content(video, transcript, comments)


async def generate_comment(
    video: VideoData,
    analysis: Dict[str, Any],
    style: str = "engaging"
) -> Dict[str, Any]:
    """
    Generate comment using OpenRouter service.
    
    Args:
        video: VideoData object
        analysis: Content analysis results
        style: Comment style
        
    Returns:
        Generated comment dictionary
    """
    async with OpenRouterService() as service:
        return await service.generate_engaging_comment(video, analysis, style) 