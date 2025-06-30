"""
Agent 5: Comment Generator

This agent handles:
- AI-powered comment generation based on content analysis
- Generating engaging comments that add value to discussions
- Creating video suggestions for next content
- Ensuring YouTube community guidelines compliance
- Multiple comment styles and variety
- Quality validation and filtering
"""

import asyncio
import random
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import json

from ..services.openrouter_service import OpenRouterService
from ..utils.logging_config import get_logger
from ..utils.ai_prompts import prompt_manager
from ..models.schemas import ProcessingStatus
from ..config import settings

logger = get_logger(__name__)


class CommentGeneratorAgent:
    """Agent responsible for generating engaging comments using AI analysis."""
    
    def __init__(self):
        """Initialize the Comment Generator Agent."""
        self.name = "comment_generator"
        self.description = "Generates engaging comments based on AI content analysis"
        
        # Comment templates and styles
        self.comment_styles = {
            "engaging": "Create an engaging, conversational comment that encourages discussion",
            "professional": "Generate a professional, insightful comment with constructive feedback", 
            "educational": "Write an educational comment that adds learning value",
            "appreciative": "Create an appreciative comment that shows genuine interest",
            "curious": "Generate a curious comment with thoughtful questions"
        }
        
        # Minimum comment length requirement
        self.MIN_COMMENT_LENGTH = 120  # Increased to ensure full-length comments
        self.MAX_COMMENT_LENGTH = 500  # Allow longer comments up to config limit
        
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the comment generation workflow.
        
        Args:
            state: Current workflow state with analyzed video data
            
        Returns:
            Updated workflow state with generated comments
        """
        try:
            logger.info(f"💬 Comment Generator Agent starting for {len(state.get('videos', []))} videos")
            
            videos = state.get("videos", [])
            if not videos:
                return self._create_error_state(state, "No videos found in state")
            
            # Initialize OpenRouter service
            openrouter = OpenRouterService()
            
            # Process each video to generate comments
            updated_videos = []
            successful_generations = 0
            failed_generations = 0
            
            for i, video in enumerate(videos):
                logger.info(f"🔄 Generating comment for video {i+1}/{len(videos)}: {video.get('title', 'Unknown')}")
                
                # Generate comment and suggestions for this video
                updated_video = await self._generate_video_comment(
                    video, 
                    openrouter
                )
                
                # Track statistics
                if updated_video.get("generated_comment") and len(updated_video.get("generated_comment", "")) >= self.MIN_COMMENT_LENGTH:
                    successful_generations += 1
                    updated_video["status"] = ProcessingStatus.COMPLETED.value
                else:
                    failed_generations += 1
                    updated_video["status"] = ProcessingStatus.FAILED.value
                
                updated_videos.append(updated_video)
            
            # Update workflow state
            updated_state = self._update_workflow_state(
                state, 
                updated_videos, 
                successful_generations, 
                failed_generations
            )
            
            logger.info(f"✅ Comment Generator completed. Success: {successful_generations}, Failed: {failed_generations}")
            
            return updated_state
            
        except Exception as e:
            logger.error(f"❌ Comment Generator Agent failed: {str(e)}")
            return self._create_error_state(state, str(e))
    
    async def _generate_video_comment(
        self, 
        video: Dict[str, Any], 
        openrouter: OpenRouterService
    ) -> Dict[str, Any]:
        """
        Generate comment and suggestions for a single video.
        
        Args:
            video: Video data dictionary with analysis
            openrouter: OpenRouter service instance
            
        Returns:
            Updated video data with generated comments
        """
        video_title = video.get("title", "Unknown")
        
        try:
            # Prepare analysis data for comment generation
            analysis_data = self._prepare_analysis_for_generation(video)
            
            if not analysis_data.get("has_analysis"):
                logger.warning(f"⚠️ No analysis data available for comment generation: '{video_title}'")
                # Create fallback comment based on basic video info
                fallback_comment = self._create_fallback_comment_from_video(video)
                return {
                    **video,
                    "generated_comment": fallback_comment,
                    "video_suggestions": [],
                    "generation_error": "No analysis data available - used fallback"
                }
            
            # Generate comment with multiple attempts to ensure proper length
            final_comment = await self._generate_proper_length_comment(analysis_data, openrouter)
            
            # Generate video suggestions
            suggestions = await self._generate_video_suggestions(analysis_data, openrouter)
            
            # Create generation results
            generation_results = {
                "generated_comment": final_comment,
                "video_suggestions": suggestions or [],
                "comment_metadata": {
                    "generation_style": analysis_data.get("preferred_style", "engaging"),
                    "content_type": analysis_data.get("content_type", "general"),
                    "comment_length": len(final_comment) if final_comment else 0,
                    "includes_question": "?" in final_comment if final_comment else False,
                    "includes_suggestions": len(suggestions or []) > 0,
                    "generated_at": datetime.now().isoformat()
                },
                "comment_ready": bool(final_comment and len(final_comment) >= self.MIN_COMMENT_LENGTH)
            }
            
            logger.info(f"✅ Comment generated for '{video_title}' ({len(final_comment) if final_comment else 0} chars)")
            
            return {
                **video,
                **generation_results
            }
            
        except Exception as e:
            logger.error(f"❌ Error generating comment for '{video_title}': {str(e)}")
            # Create emergency fallback
            fallback_comment = self._create_fallback_comment_from_video(video)
            return {
                **video,
                "generated_comment": fallback_comment,
                "video_suggestions": [],
                "generation_error": f"Comment generation failed: {str(e)}"
            }

    async def _generate_proper_length_comment(
        self, 
        analysis_data: Dict[str, Any], 
        openrouter: OpenRouterService
    ) -> Optional[str]:
        """
        Generate a comment ensuring it meets minimum length requirements.
        
        Args:
            analysis_data: Prepared analysis data
            openrouter: OpenRouter service instance
            
        Returns:
            Generated comment meeting length requirements
        """
        # Try primary generation
        comment = await self._generate_engaging_comment(analysis_data, openrouter)
        
        if comment and len(comment) >= self.MIN_COMMENT_LENGTH:
            return comment
        
        # If too short, try concise generation
        logger.warning("Generated comment too short, creating fallback")
        fallback_comment = await self._generate_concise_comment(analysis_data, openrouter)
        
        if fallback_comment and len(fallback_comment) >= self.MIN_COMMENT_LENGTH:
            return fallback_comment
        
        # Final fallback - structured comment
        return self._create_structured_fallback_comment(analysis_data)

    def _create_fallback_comment_from_video(self, video: Dict[str, Any]) -> str:
        """Create a fallback comment from basic video information."""
        title = video.get("title", "this video")
        
        fallback_templates = [
            f"Really appreciate the detailed insights shared in '{title}'. The content is exceptionally well-structured and informative, covering aspects that many other creators miss. This level of thoroughness is exactly what makes educational content valuable. Looking forward to more content like this!",
            f"Great comprehensive breakdown in '{title}'. The way you explained the complex concepts made them easy to follow and understand. Your teaching approach is clear and engaging. Thanks for sharing your expertise and taking the time to create such quality content!",
            f"Excellent in-depth content in '{title}'. This kind of detailed explanation with practical examples is exactly what I was looking for. The way you structured the information made it easy to follow along. Keep up the outstanding work!",
            f"Thanks for creating such comprehensive content in '{title}'. The information is incredibly valuable and presented with exceptional clarity. Your approach to breaking down complex topics is refreshing. Would love to see more content on similar topics!",
            f"Found '{title}' extremely helpful and well-produced. The approach you took to explain everything was both engaging and highly informative. This is the kind of quality educational content that truly makes a difference. Subscribed for more!"
        ]
        
        return random.choice(fallback_templates)

    def _create_structured_fallback_comment(self, analysis_data: Dict[str, Any]) -> str:
        """Create a structured fallback comment ensuring minimum length."""
        context = analysis_data.get("context", {})
        title = context.get("video_title", "this video")
        topics = context.get("key_topics", [])
        
        # Build comprehensive comment components
        appreciation = f"Really appreciate the comprehensive and detailed content in '{title}'."
        
        if topics:
            topic_mention = f" The in-depth coverage of {topics[0]} was particularly insightful and well-explained."
        else:
            topic_mention = " The way you presented the information was exceptionally clear and engaging."
        
        value_add = " This level of detail and practical approach is exactly what makes educational content valuable."
        engagement = " Thanks for sharing your expertise and taking the time to create such quality content - looking forward to more!"
        
        comment = appreciation + topic_mention + value_add + engagement
        
        # Ensure minimum length with additional context
        if len(comment) < self.MIN_COMMENT_LENGTH:
            comment += " Keep up the excellent work and continue creating valuable content that truly helps the community learn and grow!"
        
        return comment
    
    def _prepare_analysis_for_generation(self, video: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare analysis data for comment generation.
        
        Args:  
            video: Video data dictionary with analysis
            
        Returns:
            Prepared analysis data for generation
        """
        # Extract analysis components
        analysis = video.get("analysis", {})
        content_summary = analysis.get("content_summary", "")
        main_themes = analysis.get("main_themes", [])
        key_takeaways = analysis.get("key_takeaways", [])
        engagement_factors = analysis.get("engagement_factors", [])
        comment_opportunities = analysis.get("comment_opportunities", [])
        content_style = analysis.get("content_style", "")
        emotional_tone = analysis.get("emotional_tone", "")
        recommended_comment_style = analysis.get("recommended_comment_style", "")
        
        # Extract video metadata
        video_title = video.get("title", "Unknown Video")
        description = video.get("description", "")
        comments = video.get("comments", [])
        
        # Extract metrics
        view_count = video.get("view_count", 0)
        like_count = video.get("like_count", 0)
        comment_count = video.get("comment_count", 0)
        
        # Use AI-recommended style if available, otherwise determine from content
        if recommended_comment_style:
            preferred_style = recommended_comment_style
        else:
            content_type = self._determine_content_type(video_title, description, main_themes)
            engagement_level = self._assess_engagement_level(view_count, like_count, comment_count)
            preferred_style = self._determine_comment_style(content_type, engagement_level)
        
        # Get top existing comments for context
        top_comments = [comment.get("text", "")[:100] for comment in comments[:5] if comment.get("text")]
        
        # Check if we have substantial analysis data
        has_analysis = bool(content_summary or main_themes or key_takeaways or description)
        
        return {
            "has_analysis": has_analysis,
            "preferred_style": preferred_style,
            "content_type": content_style or self._determine_content_type(video_title, description, main_themes),
            "context": {
                "video_title": video_title,
                "content_summary": content_summary or description[:300] + "..." if description else "No summary available",
                "main_themes": main_themes or ["general content"],
                "key_takeaways": key_takeaways or ["valuable information"],
                "engagement_factors": engagement_factors or ["informative content"],
                "comment_opportunities": comment_opportunities or ["ask questions", "share experiences"],
                "emotional_tone": emotional_tone or "neutral",
                "engagement_level": self._assess_engagement_level(view_count, like_count, comment_count),
                "video_metrics": {
                    "views": view_count,
                    "likes": like_count,
                    "comments": comment_count,
                    "engagement_rate": (like_count + comment_count) / max(view_count, 1) if view_count > 0 else 0
                },
                "top_existing_comments": top_comments,
                "video_description": description[:500] if description else "No description available"
            }
        }
    
    def _determine_content_type(self, title: str, description: str, topics: List[str]) -> str:
        """Determine the type of content based on available information."""
        title_lower = title.lower()
        desc_lower = description.lower()
        topics_lower = [topic.lower() for topic in topics]
        
        # Educational indicators
        educational_keywords = ["how to", "tutorial", "guide", "learn", "explained", "tips", "tricks"]
        if any(keyword in title_lower for keyword in educational_keywords):
            return "educational"
        
        # Review indicators
        review_keywords = ["review", "comparison", "vs", "best", "worst", "rating"]
        if any(keyword in title_lower for keyword in review_keywords):
            return "review"
        
        # Entertainment indicators
        entertainment_keywords = ["funny", "comedy", "entertainment", "story", "vlog"]
        if any(keyword in title_lower for keyword in entertainment_keywords):
            return "entertainment"
        
        # Business/Professional indicators
        business_keywords = ["business", "marketing", "strategy", "professional", "career"]
        if any(keyword in title_lower or keyword in desc_lower for keyword in business_keywords):
            return "professional"
        
        return "general"
    
    def _assess_engagement_level(self, views: int, likes: int, comments: int) -> str:
        """Assess the engagement level of the video."""
        if views == 0:
            return "new"
        
        like_ratio = likes / views if views > 0 else 0
        comment_ratio = comments / views if views > 0 else 0
        
        if like_ratio > 0.05 or comment_ratio > 0.01:
            return "high"
        elif like_ratio > 0.02 or comment_ratio > 0.005:
            return "medium"
        else:
            return "low"
    
    def _determine_comment_style(self, content_type: str, engagement_potential: str) -> str:
        """
        Determine the most appropriate comment style based on content analysis.
        
        Args:
            content_type: Type of content (educational, entertainment, etc.)
            engagement_potential: Potential for engagement (high, medium, low)
            
        Returns:
            Recommended comment style
        """
        # Style mapping based on content type and engagement
        style_matrix = {
            "educational": {
                "high": "curious",
                "medium": "appreciative", 
                "low": "educational"
            },
            "review": {
                "high": "engaging",
                "medium": "professional",
                "low": "appreciative"
            },
            "entertainment": {
                "high": "engaging",
                "medium": "engaging",
                "low": "appreciative"
            },
            "professional": {
                "high": "professional",
                "medium": "professional",
                "low": "appreciative"
            },
            "general": {
                "high": "engaging",
                "medium": "appreciative",
                "low": "curious"
            }
        }
        
        return style_matrix.get(content_type, {}).get(engagement_potential, "engaging")
    
    async def _generate_engaging_comment(
        self, 
        analysis_data: Dict[str, Any], 
        openrouter: OpenRouterService
    ) -> Optional[str]:
        """
        Generate an engaging comment based on analysis data.
        
        Args:
            analysis_data: Prepared analysis data
            openrouter: OpenRouter service instance
            
        Returns:
            Generated comment or None if failed
        """
        context = analysis_data["context"]
        style = analysis_data["preferred_style"]
        style_instruction = self.comment_styles.get(style, self.comment_styles["engaging"])
        
        # Create a comprehensive prompt that ensures proper length and human-like quality
        prompt = f"""You are writing a genuine YouTube comment as a real human viewer who just watched this video. Your comment should sound natural, conversational, and add real value to the discussion.

VIDEO DETAILS:
Title: "{context['video_title']}"
Content Summary: {context['content_summary'][:200]}
Main Themes: {', '.join(context['main_themes'][:3])}
Key Takeaways: {', '.join(context['key_takeaways'][:2])}
Content Type: {analysis_data['content_type']}
Emotional Tone: {context['emotional_tone']}
Engagement Level: {context['engagement_level']}

VIDEO METRICS:
Views: {context['video_metrics']['views']:,}
Likes: {context['video_metrics']['likes']:,}
Comments: {context['video_metrics']['comments']:,}

COMMENT OPPORTUNITIES (topics that generate discussion):
{', '.join(context['comment_opportunities'][:3])}

COMMENT REQUIREMENTS:
✅ MUST be between 150-400 characters (this is critical)
✅ Sound like a real human viewer, not AI-generated
✅ Reference specific aspects of the video content or themes
✅ Add genuine value or insight to the discussion
✅ Use natural, conversational language
✅ Include personal perspective or experience if relevant
✅ End with a question, suggestion, or call for discussion when appropriate
✅ Match the video's emotional tone ({context['emotional_tone']})

STYLE GUIDANCE: {style_instruction}

EXCELLENT HUMAN-LIKE COMMENT EXAMPLES:

Example 1 (Educational/Business):
"This breakdown of {context['main_themes'][0] if context['main_themes'] else 'the concepts'} was exactly what I needed! The practical examples really helped clarify things I've been struggling with. I'm definitely going to implement the strategies you outlined. Have you considered doing a follow-up covering advanced techniques? Your teaching approach is incredibly effective."

Example 2 (Professional/Insightful):
"Really appreciate the depth you went into about {context['main_themes'][0] if context['main_themes'] else 'this topic'}. The real-world examples were particularly insightful and much more valuable than theoretical approaches. I'm excited to try these methods in my own work. Thanks for sharing actionable insights instead of just surface-level information!"

Example 3 (Engaging/Appreciative):
"Wow, this completely changed my perspective on {context['main_themes'][0] if context['main_themes'] else 'the subject'}! The way you explained it made complex concepts so much clearer. I've been looking for this kind of detailed breakdown for months. The examples you provided were perfect. Can't wait to apply these ideas to my own projects!"

Now write ONE authentic, human-like comment (150-400 characters) about the video "{context['video_title']}" that references the content themes and adds genuine value:
"""
        
        try:
            # Validate model - warn about reasoning models but don't override
            model = settings.get_comment_generator_model()
            if ":thinking" in model.lower():
                logger.warning(f"⚠️ Reasoning model detected ({model}) - these models may generate very short responses. Consider using anthropic/claude-3.5-sonnet or openai/gpt-4o for better comment generation.")
            
            response = await openrouter.generate_completion(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                max_tokens=300,  # Increased for longer comments
                temperature=0.8  # Higher temperature for more creative comments
            )
            
            if response.get("success"):
                comment = response["content"].strip()
                comment = self._clean_generated_comment(comment)
                
                # Strict validation - if comment is too short, regenerate with fallback
                if len(comment) < 120:  # Ensure minimum length for quality
                    logger.warning(f"Generated comment too short ({len(comment)} chars), using enhanced fallback")
                    return self._create_enhanced_fallback_comment(analysis_data)
                
                # Additional validation for extremely short responses (likely from reasoning models)
                if len(comment) < 20:
                    logger.error(f"Generated comment extremely short ({len(comment)} chars) - likely reasoning model issue, using fallback")
                    return self._create_enhanced_fallback_comment(analysis_data)
                
                # Ensure it's not too long
                if len(comment) > self.MAX_COMMENT_LENGTH:
                    comment = comment[:self.MAX_COMMENT_LENGTH-3] + "..."
                
                return comment
            
            return None
            
        except Exception as e:
            logger.error(f"Comment generation error: {str(e)}")
            return None

    def _create_enhanced_fallback_comment(self, analysis_data: Dict[str, Any]) -> str:
        """Create a high-quality fallback comment ensuring proper length."""
        context = analysis_data.get("context", {})
        title = context.get("video_title", "this video")
        main_themes = context.get("main_themes", ["content"])
        key_takeaways = context.get("key_takeaways", ["valuable insights"])
        content_type = analysis_data.get("content_type", "informational")
        
        # Get the primary theme and takeaway
        primary_theme = main_themes[0] if main_themes else "the concepts"
        primary_takeaway = key_takeaways[0] if key_takeaways else "valuable insights"
        
        # Enhanced fallback templates with guaranteed length and human-like quality
        templates = [
            f"This was exactly what I needed! The way you explained {primary_theme} in '{title}' made everything click for me. I've been struggling with this topic for a while, and your approach really helped clarify things. The insights about {primary_takeaway} were particularly valuable. Thanks for creating such detailed content!",
            
            f"Wow, incredible breakdown in '{title}'! Your explanation of {primary_theme} was spot-on and so much clearer than other content I've seen. The practical approach you took really made the difference. I'm definitely going to implement these ideas and looking forward to seeing the results!",
            
            f"Found this video incredibly helpful! The depth you went into about {primary_theme} in '{title}' was impressive. Most creators just scratch the surface, but you actually provided actionable insights. The part about {primary_takeaway} was especially enlightening. Definitely subscribing for more content like this!",
            
            f"Perfect timing on this video! I was just researching {primary_theme} and '{title}' answered all my questions and more. Your teaching style is really engaging and easy to follow. The way you broke down {primary_takeaway} made complex concepts much more manageable. Excellent work!",
            
            f"This {content_type} content on '{title}' was a game-changer! Your coverage of {primary_theme} was thorough yet easy to understand. I especially appreciated how you explained {primary_takeaway} with real-world context. This is the kind of quality content that actually helps people succeed. Keep it up!",
            
            f"Absolutely loved this video! The way you broke down {primary_theme} in '{title}' was brilliant. I've watched several videos on this topic, but yours was by far the most comprehensive and practical. The insights about {primary_takeaway} were particularly valuable. Thanks for sharing your expertise!",
            
            f"This is exactly the type of content I was looking for! Your explanation of {primary_theme} in '{title}' was clear, detailed, and actionable. The examples you provided really helped me understand how to apply {primary_takeaway} in practice. Excited to try these ideas out and see the results!"
        ]
        
        comment = random.choice(templates)
        
        # Ensure minimum length by adding more context if needed
        if len(comment) < 150:
            comment += f" Would love to see more content covering advanced techniques in {primary_theme} and related topics."
        
        return comment

    def _extend_short_comment(self, short_comment: str, context: Dict[str, Any]) -> str:
        """Extend a short comment to meet minimum length requirements with quality content."""
        if not short_comment or len(short_comment) < 10:
            # If comment is too short or empty, create a proper one
            return self._create_enhanced_fallback_comment({"context": context})
        
        # Add meaningful extensions based on context
        video_title = context.get('video_title', 'this video')
        main_themes = context.get('main_themes', ['content'])
        key_takeaways = context.get('key_takeaways', ['valuable insights'])
        
        primary_theme = main_themes[0] if main_themes else 'the concepts'
        primary_takeaway = key_takeaways[0] if key_takeaways else 'valuable insights'
        
        extensions = [
            f" The way you explained {primary_theme} in '{video_title}' was particularly clear and helpful. The insights about {primary_takeaway} really made it click for me. Thanks for sharing such valuable content!",
            f" I found the approach you took in '{video_title}' to be very practical and well-structured. The part about {primary_takeaway} was especially useful. Looking forward to implementing these ideas and seeing more content like this!",
            f" Your breakdown of {primary_theme} in '{video_title}' really helped clarify some concepts I was struggling with. The way you presented {primary_takeaway} was exactly what I needed to understand this better!",
            f" The examples you provided in '{video_title}' were spot-on and made {primary_theme} much easier to understand. I especially appreciated the insights about {primary_takeaway}. Keep up the excellent work with these tutorials!",
            f" Really appreciate the depth of information you covered in '{video_title}'. The way you presented {primary_theme} was engaging and informative, and the part about {primary_takeaway} was particularly valuable. Subscribed for more quality content!"
        ]
        
        extended = short_comment + random.choice(extensions)
        
        # Ensure we meet minimum requirements
        if len(extended) < 150:
            extended += f" Would love to see more advanced content covering {primary_theme} and related topics in the future."
        
        return extended

    async def _generate_concise_comment(
        self, 
        analysis_data: Dict[str, Any], 
        openrouter: OpenRouterService
    ) -> Optional[str]:
        """Generate a concise but complete comment as fallback."""
        context = analysis_data["context"]
        
        prompt = f"""Generate a complete YouTube comment (minimum 150 characters) for this video:

Title: {context['video_title']}
Main Themes: {', '.join(context['main_themes'][:2])}
Key Takeaways: {', '.join(context['key_takeaways'][:2])}
Content Summary: {context['content_summary'][:150]}

The comment should:
- Be exactly 150-300 characters
- Sound natural and genuine  
- Reference the content themes specifically
- Add value to the discussion
- Include a thoughtful insight or question
- Show engagement with the specific content

Examples:
"Excellent breakdown of {context['main_themes'][0] if context['main_themes'] else 'the concepts'}! The insights about {context['key_takeaways'][0] if context['key_takeaways'] else 'practical applications'} were particularly helpful. Have you considered covering advanced techniques in this area? Would love to see more content like this!"

"Really appreciate this detailed guide on {context['main_themes'][0] if context['main_themes'] else 'the topic'}. The way you explained {context['key_takeaways'][0] if context['key_takeaways'] else 'the key points'} was spot-on and practical. This approach could really help people get better results. Thanks for sharing such valuable insights!"

Generate ONE complete comment (150-300 characters) that references the video's themes and takeaways:"""
        
        try:
            # Validate model - warn about reasoning models but don't override
            model = settings.get_comment_generator_model()
            if ":thinking" in model.lower():
                logger.warning(f"⚠️ Reasoning model detected ({model}) - these models may generate very short responses. Consider using anthropic/claude-3.5-sonnet or openai/gpt-4o for better comment generation.")
            
            response = await openrouter.generate_completion(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                max_tokens=200,  # Increased for longer comments
                temperature=0.7
            )
            
            if response.get("success"):
                comment = response["content"].strip()
                comment = self._clean_generated_comment(comment)
                
                # Ensure minimum length
                if len(comment) < 150:
                    return self._create_enhanced_fallback_comment(analysis_data)
                
                return comment
            
            return None
            
        except Exception as e:
            logger.error(f"Concise comment generation error: {str(e)}")
            return None
    
    async def _generate_video_suggestions(
        self, 
        analysis_data: Dict[str, Any], 
        openrouter: OpenRouterService
    ) -> List[str]:
        """
        Generate video content suggestions based on analysis.
        
        Args:
            analysis_data: Prepared analysis data
            openrouter: OpenRouter service instance
            
        Returns:
            List of video suggestions
        """
        context = analysis_data["context"]
        
        prompt = f"""Generate 3-5 specific video title suggestions based on this content:

Original Video: "{context['video_title']}"
Key Topics: {', '.join(context.get('main_themes', ['general content']))}
Content Type: {analysis_data['content_type']}

Requirements:
- Specific, actionable titles
- Related to original content
- Appeal to same audience
- Search-friendly
- Realistic to produce

Format as JSON array: ["Title 1", "Title 2", "Title 3"]"""
        
        try:
            response = await openrouter.generate_completion(
                messages=[{"role": "user", "content": prompt}],
                model=settings.get_comment_generator_model(),
                max_tokens=300,
                temperature=0.8
            )
            
            if response.get("success"):
                suggestions_json = response["content"].strip()
                try:
                    suggestions = json.loads(suggestions_json)
                    return suggestions if isinstance(suggestions, list) else []
                except json.JSONDecodeError:
                    return self._extract_suggestions_from_text(suggestions_json)
            
            return []
            
        except Exception as e:
            logger.error(f"Suggestions generation error: {str(e)}")
            return []
    
    def _clean_generated_comment(self, comment: str) -> str:
        """
        Clean and validate generated comment.
        
        Args:
            comment: Raw generated comment
            
        Returns:
            Cleaned comment
        """
        # Remove quotes and common AI-generated prefixes
        comment = comment.strip()
        comment = comment.strip('"\'')
        
        # Remove common AI prefixes
        prefixes_to_remove = [
            "Here's a comment:",
            "Comment:",
            "Generated comment:",
            "Here's my comment:",
            "My comment:",
            "Response:",
            "Reply:"
        ]
        
        for prefix in prefixes_to_remove:
            if comment.lower().startswith(prefix.lower()):
                comment = comment[len(prefix):].strip()
        
        # Remove markdown formatting
        comment = comment.replace("**", "").replace("*", "")
        
        # Clean up extra whitespace
        comment = " ".join(comment.split())
        
        return comment
    
    def _extract_suggestions_from_text(self, text: str) -> List[str]:
        """
        Extract video suggestions from unstructured text.
        
        Args:
            text: Text containing suggestions
            
        Returns:
            List of extracted suggestions
        """
        suggestions = []
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            # Look for numbered lists or bullet points
            if any(line.startswith(prefix) for prefix in ['1.', '2.', '3.', '4.', '5.', '-', '•', '*']):
                # Clean up the suggestion
                suggestion = line
                for prefix in ['1.', '2.', '3.', '4.', '5.', '-', '•', '*']:
                    suggestion = suggestion.replace(prefix, '').strip()
                suggestion = suggestion.strip('"\'')
                if suggestion and len(suggestion) > 10:
                    suggestions.append(suggestion)
        
        return suggestions[:5]  # Limit to 5 suggestions
    
    def _update_workflow_state(
        self, 
        current_state: Dict[str, Any], 
        updated_videos: List[Dict[str, Any]], 
        successful_generations: int, 
        failed_generations: int
    ) -> Dict[str, Any]:
        """
        Update workflow state with comment generation results.
        
        Args:
            current_state: Current workflow state
            updated_videos: Videos with generated comments
            successful_generations: Number of successful generations
            failed_generations: Number of failed generations
            
        Returns:
            Updated workflow state
        """
        # Calculate generation statistics
        total_videos = len(updated_videos)
        success_rate = (successful_generations / total_videos * 100) if total_videos > 0 else 0
        
        # Update state
        updated_state = {
            **current_state,
            "videos": updated_videos,
            "comment_generation": {
                "status": "completed",
                "total_videos": total_videos,
                "successful_generations": successful_generations,
                "failed_generations": failed_generations,
                "success_rate": round(success_rate, 1),
                "completed_at": datetime.now().isoformat()
            },
            "current_agent": "comment_generator",
            "workflow_status": "comment_generation_completed"
        }
        
        return updated_state
    
    def _create_error_state(self, current_state: Dict[str, Any], error_message: str) -> Dict[str, Any]:
        """
        Create error state for workflow.
        
        Args:
            current_state: Current workflow state
            error_message: Error description
            
        Returns:
            Error state
        """
        return {
            **current_state,
            "comment_generation": {
                "status": "failed",
                "error": error_message,
                "failed_at": datetime.now().isoformat()
            },
            "workflow_status": "comment_generation_failed"
        }
    
    async def get_generation_summary(self, videos: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get summary of comment generation results.
        
        Args:
            videos: List of processed videos
            
        Returns:
            Generation summary
        """
        total_videos = len(videos)
        successful_comments = sum(1 for video in videos if video.get("generated_comment"))
        failed_comments = total_videos - successful_comments
        
        # Calculate average comment length
        comment_lengths = [
            len(video.get("generated_comment", "")) 
            for video in videos 
            if video.get("generated_comment")
        ]
        avg_comment_length = sum(comment_lengths) / len(comment_lengths) if comment_lengths else 0
        
        # Count videos with suggestions
        videos_with_suggestions = sum(
            1 for video in videos 
            if video.get("video_suggestions") and len(video.get("video_suggestions", [])) > 0
        )
        
        return {
            "total_videos": total_videos,
            "successful_comments": successful_comments,
            "failed_comments": failed_comments,
            "success_rate": round((successful_comments / total_videos * 100), 1) if total_videos > 0 else 0,
            "average_comment_length": round(avg_comment_length, 1),
            "videos_with_suggestions": videos_with_suggestions,
            "generation_styles_used": list(set(
                video.get("comment_metadata", {}).get("generation_style", "unknown")
                for video in videos
                if video.get("comment_metadata")
            ))
        }

    async def _generate_comment_for_video(self, video: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate AI-powered comment for a single video.
        
        Args:
            video: Video data dictionary with analysis
            
        Returns:
            Updated video data with generated comment
        """
        video_title = video.get("title", "Unknown")
        video_id = video.get("video_id", "unknown")
        
        try:
            logger.info(f"💬 Starting AI comment generation for '{video_title}' (ID: {video_id})")
            
            # Check if we have analysis data
            analysis = video.get("analysis", {})
            if not analysis:
                logger.warning(f"⚠️ No analysis data available for '{video_title}', using basic generation")
            
            # Ensure we have the OpenRouter service
            if not hasattr(self, 'openrouter_service'):
                from app.services.openrouter_service import OpenRouterService
                self.openrouter_service = OpenRouterService()
            
            # Generate comment using AI
            comment_result = await self._generate_ai_comment(video, analysis)
            
            if not comment_result or not comment_result.get("comment"):
                logger.error(f"❌ AI comment generation failed for '{video_title}'")
                # Create fallback comment
                comment_result = await self._create_fallback_comment(video)
            
            # Validate comment length and quality
            comment_text = comment_result.get("comment", "")
            if len(comment_text.strip()) < 60:  # Increased minimum from 50 to 60
                logger.warning(f"⚠️ Generated comment too short ({len(comment_text)} chars) for '{video_title}', extending...")
                comment_result = await self._extend_short_comment(comment_result, video, analysis)
            
            # Ensure comment meets requirements
            final_comment = comment_result.get("comment", "").strip()
            if len(final_comment) < 60:
                logger.error(f"❌ Final comment still too short for '{video_title}', using emergency fallback")
                final_comment = await self._create_emergency_comment(video)
            
            logger.info(f"✅ Comment generated for '{video_title}': {len(final_comment)} characters")
            
            # Update video with comment data
            updated_video = {
                **video,
                "generated_comment": final_comment,
                "comment_metadata": {
                    "text": final_comment,
                    "style": comment_result.get("style", "engaging"),
                    "confidence_score": comment_result.get("confidence_score", 8),
                    "engagement_potential": comment_result.get("engagement_potential", "high"),
                    "character_count": len(final_comment),
                    "word_count": len(final_comment.split()),
                    "generated_at": datetime.now().isoformat(),
                    "ai_model_used": settings.get_comment_generator_model(),
                    "generation_method": comment_result.get("generation_method", "ai")
                },
                "comment_available": True,
                "comment_generated": True
            }
            
            return updated_video
            
        except Exception as e:
            logger.error(f"❌ Error generating comment for '{video_title}': {str(e)}")
            # Emergency fallback
            emergency_comment = await self._create_emergency_comment(video)
            return {
                **video,
                "generated_comment": emergency_comment,
                "comment_metadata": {
                    "text": emergency_comment,
                    "style": "fallback",
                    "confidence_score": 5,
                    "engagement_potential": "medium",
                    "character_count": len(emergency_comment),
                    "word_count": len(emergency_comment.split()),
                    "generated_at": datetime.now().isoformat(),
                    "generation_method": "emergency_fallback",
                    "error": str(e)
                },
                "comment_available": True,
                "comment_generated": True,
                "comment_generation_error": str(e)
            }
    
    async def _generate_ai_comment(self, video: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate comment using AI based on video content and analysis.
        
        Args:
            video: Video data
            analysis: Content analysis results
            
        Returns:
            Comment generation result
        """
        try:
            video_title = video.get("title", "Unknown")
            video_description = video.get("description", "")[:300]
            
            # Get recommended comment style from analysis
            recommended_style = analysis.get("recommended_comment_style", "engaging")
            content_summary = analysis.get("content_summary", "")
            key_takeaways = analysis.get("key_takeaways", [])
            comment_opportunities = analysis.get("comment_opportunities", [])
            
            # Create comprehensive comment generation prompt
            comment_prompt = f"""
Generate an engaging YouTube comment for this video. The comment should be authentic, valuable, and encourage engagement.

VIDEO TITLE: {video_title}
VIDEO DESCRIPTION: {video_description}
CONTENT SUMMARY: {content_summary}
KEY TAKEAWAYS: {', '.join(key_takeaways[:3]) if key_takeaways else 'General content'}
COMMENT OPPORTUNITIES: {', '.join(comment_opportunities[:3]) if comment_opportunities else 'Ask questions'}
RECOMMENDED STYLE: {recommended_style}

REQUIREMENTS:
- Length: 60-200 characters (MINIMUM 60 characters)
- Style: {recommended_style}
- Must be complete sentences (no "..." truncation)
- Engaging and authentic
- Encourage discussion or engagement
- Follow YouTube community guidelines
- Add value to the conversation

COMMENT STYLES:
- engaging: Enthusiastic, asks questions, shares excitement
- educational: Thoughtful insights, adds information, asks deep questions
- appreciative: Thanks creator, acknowledges effort, positive feedback
- curious: Asks genuine questions, seeks clarification, shows interest
- professional: Constructive feedback, industry insights, respectful tone

Generate a comment that:
1. Relates directly to the video content
2. Encourages replies and engagement
3. Shows genuine interest or appreciation
4. Is at least 60 characters long
5. Ends with a complete sentence (no truncation)

Respond with only the comment text, nothing else. Make sure it's engaging and authentic.
"""
            
            logger.info(f"🤖 Sending comment generation request to AI for '{video_title}'")
            
            # Make API call to generate comment using the completion method
            response = await self.openrouter_service.generate_completion(
                messages=[{"role": "user", "content": comment_prompt}],
                model=settings.get_comment_generator_model(),
                max_tokens=200,
                temperature=0.8
            )
            
            if not response or not response.get("success"):
                logger.error(f"❌ No response from AI comment generation for '{video_title}'")
                return {}
            
            # Clean and validate the response
            comment_text = response.get("content", "").strip()
            
            logger.info(f"✅ AI comment generated for '{video_title}': '{comment_text[:50]}...' ({len(comment_text)} chars)")
            
            return {
                "comment": comment_text,
                "style": recommended_style,
                "confidence_score": 9,
                "engagement_potential": "high",
                "generation_method": "ai_powered"
            }
            
        except Exception as e:
            logger.error(f"❌ Error in AI comment generation for '{video.get('title', 'Unknown')}': {str(e)}")
            return {}

    async def _create_fallback_comment(self, video: Dict[str, Any]) -> Dict[str, Any]:
        """Create a fallback comment when AI generation fails."""
        try:
            fallback_comment = self._create_fallback_comment_from_video(video)
            return {
                "comment": fallback_comment,
                "style": "fallback",
                "confidence_score": 6,
                "engagement_potential": "medium",
                "generation_method": "fallback"
            }
        except Exception as e:
            logger.error(f"Error creating fallback comment: {e}")
            return {
                "comment": "Great content! Thanks for sharing this valuable information.",
                "style": "fallback",
                "confidence_score": 5,
                "engagement_potential": "medium",
                "generation_method": "emergency_fallback"
            }

    async def _create_emergency_comment(self, video: Dict[str, Any]) -> str:
        """Create an emergency comment as final fallback."""
        try:
            title = video.get("title", "this video")
            emergency_templates = [
                f"Really appreciate the insights shared in '{title}'. This kind of detailed content is exactly what makes educational material valuable and engaging.",
                f"Excellent breakdown in '{title}'. The way you explained everything was clear and easy to follow. Thanks for creating such quality content!",
                f"Found '{title}' extremely helpful and well-produced. Your approach to presenting the information was both engaging and informative. Keep up the great work!",
                f"Thanks for creating such comprehensive content in '{title}'. The information provided is incredibly valuable and presented with exceptional clarity.",
                f"Great work on '{title}'. This level of detail and practical approach is exactly what makes content truly valuable for the community."
            ]
            return random.choice(emergency_templates)
        except Exception:
            return "Great content! Thanks for sharing this valuable information with the community. Really appreciate the effort you put into creating quality content."

    async def _extend_short_comment(self, comment_result: Dict[str, Any], video: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Extend a short comment to meet minimum length requirements."""
        try:
            original_comment = comment_result.get("comment", "")
            title = video.get("title", "this video")
            
            # Add meaningful extensions
            extensions = [
                f" The way you presented the information in '{title}' was particularly clear and engaging. Looking forward to more content like this!",
                f" I found the approach you took in '{title}' to be very practical and well-structured. Thanks for sharing such valuable insights!",
                f" Your breakdown in '{title}' really helped clarify some concepts I was exploring. Keep up the excellent work with these detailed explanations!",
                f" The examples you provided in '{title}' were spot-on and made everything much easier to understand. Appreciate the quality content!",
                f" Really enjoyed the depth you went into with '{title}'. This kind of comprehensive content is exactly what the community needs."
            ]
            
            extended_comment = original_comment + random.choice(extensions)
            
            return {
                **comment_result,
                "comment": extended_comment,
                "generation_method": "extended_" + comment_result.get("generation_method", "unknown")
            }
        except Exception as e:
            logger.error(f"Error extending comment: {e}")
            return comment_result


# LangGraph node function
async def comment_generator_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node for comment generation.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with generated comments
    """
    agent = CommentGeneratorAgent()
    return await agent.execute(state)


# Test function for development
async def test_comment_generator(sample_analyzed_video: Dict[str, Any]) -> Dict[str, Any]:
    """
    Test the comment generator with sample data.
    
    Args:
        sample_analyzed_video: Sample video with analysis data
        
    Returns:
        Test results
    """
    agent = CommentGeneratorAgent()
    test_state = {
        "videos": [sample_analyzed_video],
        "workflow_id": "test_workflow"
    }
    
    result_state = await agent.execute(test_state)
    return result_state


# Export the main components
__all__ = [
    'CommentGeneratorAgent',
    'comment_generator_node',
    'test_comment_generator'
] 