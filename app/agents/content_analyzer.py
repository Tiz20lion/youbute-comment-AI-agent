"""
Agent 4: Content Analyzer

This agent handles:
- AI-powered analysis of video transcripts, descriptions, and comments
- Content summarization and key topic extraction
- Audience sentiment analysis and engagement patterns
- Trend identification and content insights
- Preparing analysis for comment generation
"""

import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import json

from ..services.openrouter_service import OpenRouterService
from ..utils.logging_config import get_logger
from ..utils.ai_prompts import prompt_manager
from ..models.schemas import ProcessingStatus
from ..config import settings

logger = get_logger(__name__)


class ContentAnalyzerAgent:
    """Agent responsible for AI-powered content analysis using OpenRouter."""
    
    def __init__(self):
        """Initialize the Content Analyzer Agent."""
        self.name = "content_analyzer"
        self.description = "Analyzes video content using AI for insights and summaries"
        
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the content analysis workflow.
        
        Args:
            state: Current workflow state with video data
            
        Returns:
            Updated workflow state with AI analysis
        """
        try:
            logger.info(f"🧠 Content Analyzer Agent starting for {len(state.get('videos', []))} videos")
            
            videos = state.get("videos", [])
            if not videos:
                return self._create_error_state(state, "No videos found in state")
            
            # Initialize OpenRouter service
            openrouter = OpenRouterService()
            
            # Process each video for AI analysis
            updated_videos = []
            successful_analyses = 0
            failed_analyses = 0
            
            for i, video in enumerate(videos):
                logger.info(f"🔄 Analyzing video {i+1}/{len(videos)}: {video.get('title', 'Unknown')}")
                
                # Analyze content for this video
                analyzed_video = await self._analyze_video_content(video)
                
                # Track statistics
                if analyzed_video.get("analysis"):
                    successful_analyses += 1
                    analyzed_video["status"] = ProcessingStatus.COMPLETED.value
                else:
                    failed_analyses += 1
                    analyzed_video["status"] = ProcessingStatus.FAILED.value
                
                updated_videos.append(analyzed_video)
            
            # Generate overall channel analysis
            channel_analysis = await self._analyze_channel_content(
                updated_videos, 
                state.get("channel_data", {}), 
                openrouter
            )
            
            # Update workflow state
            updated_state = self._update_workflow_state(
                state, 
                updated_videos, 
                channel_analysis,
                successful_analyses, 
                failed_analyses
            )
            
            logger.info(f"✅ Content Analyzer completed. Success: {successful_analyses}, Failed: {failed_analyses}")
            
            return updated_state
            
        except Exception as e:
            logger.error(f"❌ Content Analyzer Agent failed: {str(e)}")
            return self._create_error_state(state, str(e))
    
    async def _analyze_video_content(self, video: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze content for a single video using AI.
        
        Args:
            video: Video data dictionary
            
        Returns:
            Updated video data with analysis results
        """
        video_title = video.get("title", "Unknown")
        video_id = video.get("video_id", "unknown")
        
        try:
            logger.info(f"🧠 Starting AI analysis for '{video_title}' (ID: {video_id})")
            
            # Prepare content for analysis
            content_data = self._prepare_content_for_analysis(video)
            
            if not content_data.get("has_content", False):
                logger.warning(f"⚠️ Insufficient content for analysis: '{video_title}'")
                return self._handle_analysis_fallback(video, "Insufficient content for analysis")
            
            content_to_analyze = content_data.get("content", "")
            if len(content_to_analyze.strip()) < 20:
                logger.warning(f"⚠️ Content too short for analysis: '{video_title}'")
                return self._handle_analysis_fallback(video, "Content too short for analysis")
            
            logger.info(f"📊 Analyzing {len(content_to_analyze)} characters of content for '{video_title}'")
            
            # Generate comprehensive analysis using AI
            analysis_result = await self._generate_comprehensive_analysis(content_to_analyze, video)
            
            if not analysis_result:
                logger.error(f"❌ AI analysis failed for '{video_title}'")
                return self._handle_analysis_fallback(video, "AI analysis failed")
            
            logger.info(f"✅ AI analysis completed for '{video_title}' - Generated {len(str(analysis_result))} chars of analysis")
            
            # Update video with analysis results
            updated_video = {
                **video,
                "analysis": analysis_result,
                "analysis_available": True,
                "analyzed_at": datetime.now().isoformat(),
                "content_length_analyzed": len(content_to_analyze)
            }
            
            return updated_video
            
        except Exception as e:
            logger.error(f"❌ Error analyzing content for '{video_title}': {str(e)}")
            return self._handle_analysis_fallback(video, f"Analysis error: {str(e)}")
    
    def _prepare_content_for_analysis(self, video: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare video content for AI analysis.
        
        Args:
            video: Video data dictionary
            
        Returns:
            Prepared content structure
        """
        content_parts = []
        
        # Video metadata
        title = video.get("title", "")
        description = video.get("description", "")
        
        if title:
            content_parts.append(f"Title: {title}")
        
        # Use description as primary content (no duplicate entries)
        if description and len(description.strip()) > 0:
            # Use substantial portion of description for analysis
            content_parts.append(f"Video Description: {description[:2000]}")  # Increased for better analysis
        else:
            content_parts.append("Video Description: No description available")
        
        # Video metrics for context
        view_count = video.get("view_count", 0)
        like_count = video.get("like_count", 0)
        comment_count = video.get("comment_count", 0)
        
        content_parts.append(f"Video Metrics: {view_count:,} views, {like_count:,} likes, {comment_count:,} comments")
        
        # Published date for context
        published_at = video.get("published_at", "")
        if published_at:
            content_parts.append(f"Published: {published_at}")
        
        # Duration for context
        duration = video.get("duration", "")
        if duration:
            content_parts.append(f"Duration: {duration}")
        
        # Top comments for audience insights
        comments = video.get("comments", [])
        if comments:
            top_comments = comments[:8]  # Use top 8 comments for context
            comments_text = []
            for comment in top_comments:
                comment_text = comment.get("text", "")[:150]  # Limit comment length
                if comment_text and len(comment_text.strip()) > 10:
                    comments_text.append(comment_text.strip())
            
            if comments_text:
                content_parts.append(f"Top Audience Comments: {' | '.join(comments_text)}")
        
        # Tags for additional context
        tags = video.get("tags", [])
        if tags:
            content_parts.append(f"Video Tags: {', '.join(tags[:15])}")
        
        # Category for context
        category = video.get("category", "")
        if category:
            content_parts.append(f"Category: {category}")
        
        return {
            "has_content": len(content_parts) > 1,  # Must have more than just title
            "content": "\n\n".join(content_parts),
            "video_id": video.get("video_id", ""),
            "title": title,
            "description_length": len(description) if description else 0,
            "has_substantial_description": len(description.strip()) > 100 if description else False,
            "metrics": {
                "view_count": view_count,
                "like_count": like_count,
                "comment_count": comment_count,
                "engagement_rate": (like_count + comment_count) / max(view_count, 1) if view_count > 0 else 0
            }
        }
    
    async def _generate_comprehensive_analysis(self, content: str, video: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generate comprehensive AI analysis of video content.
        
        Args:
            content: Content to analyze
            video: Video metadata
            
        Returns:
            Analysis results or None if failed
        """
        try:
            # Ensure we have the OpenRouter service
            if not hasattr(self, 'openrouter_service'):
                from app.services.openrouter_service import OpenRouterService
                self.openrouter_service = OpenRouterService()
            
            video_title = video.get("title", "Unknown")
            
            # Create comprehensive analysis prompt
            analysis_prompt = f"""You are a JSON API. Return ONLY valid JSON, no other text.

Analyze this YouTube video content:

VIDEO TITLE: {video_title}
VIDEO DESCRIPTION: {video.get('description', 'No description available')[:500]}
CONTENT: {content[:3000]}

Return ONLY this JSON structure (no markdown, no explanations, no other text):

{{
    "main_themes": ["list", "of", "3-5", "key", "topics"],
    "content_summary": "2-3 sentence summary of the main content",
    "audience_insights": "Description of who this content is for",
    "engagement_factors": ["what", "makes", "this", "engaging"],
    "key_takeaways": ["main", "points", "viewers", "learn"],
    "content_style": "educational|entertainment|informational|news|tutorial",
    "emotional_tone": "positive|neutral|inspiring|urgent|analytical",
    "comment_opportunities": ["topics", "that", "generate", "discussion"],
    "overall_quality_score": 8,
    "recommended_comment_style": "engaging"
}}"""
            
            logger.info(f"🤖 Sending content to AI for analysis: '{video_title}'")
            
            # Make API call to OpenRouter using the correct method
            response = await self.openrouter_service.generate_completion(
                messages=[{"role": "user", "content": analysis_prompt}],
                model=settings.get_content_analyzer_model(),
                max_tokens=800,
                temperature=0.3
            )
            
            if not response or not response.get("success"):
                logger.error(f"❌ No response from AI analysis for '{video_title}'")
                return None
            
            # Get the content from the response
            content_response = response.get("content", "")
            logger.info(f"✅ AI analysis response received for '{video_title}': {len(str(content_response))} chars")
            
            # Validate and structure the response
            try:
                import json
                analysis_result = json.loads(content_response)
                logger.info(f"✅ Successfully parsed AI response as JSON for '{video_title}'")
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"⚠️ Could not parse AI response as JSON for '{video_title}': {str(e)}")
                logger.debug(f"Raw AI response: {content_response[:200]}...")
                
                # Try to extract meaningful content from non-JSON response
                fallback_summary = str(content_response)[:500] if content_response else "No analysis available"
                
                analysis_result = {
                    "content_summary": fallback_summary,
                    "main_themes": ["General content"],
                    "audience_insights": "General audience",
                    "engagement_factors": ["Informative content"],
                    "key_takeaways": ["Valuable information"],
                    "content_style": "informational",
                    "emotional_tone": "neutral",
                    "comment_opportunities": ["Ask questions", "Share experiences"],
                    "overall_quality_score": 7,
                    "recommended_comment_style": "engaging",
                    "fallback_used": True,
                    "parsing_error": str(e)
                }
            
            # Ensure all required fields are present
            required_fields = [
                "main_themes", "content_summary", "audience_insights", 
                "engagement_factors", "key_takeaways", "content_style",
                "emotional_tone", "comment_opportunities", "overall_quality_score",
                "recommended_comment_style"
            ]
            
            for field in required_fields:
                if field not in analysis_result:
                    logger.warning(f"⚠️ Missing field '{field}' in analysis for '{video_title}', adding default")
                    analysis_result[field] = "Not analyzed" if field not in ["overall_quality_score"] else 5
            
            # Add metadata
            analysis_result.update({
                "analysis_timestamp": datetime.now().isoformat(),
                "content_length": len(content),
                "ai_model_used": settings.get_content_analyzer_model(),
                "analysis_version": "1.0"
            })
            
            logger.info(f"✅ Structured analysis completed for '{video_title}' with {len(analysis_result)} fields")
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"❌ Error in AI analysis generation for '{video.get('title', 'Unknown')}': {str(e)}")
            return None
    async def _analyze_channel_content(
        self, 
        videos: List[Dict[str, Any]], 
        channel_data: Dict[str, Any], 
        openrouter: OpenRouterService
    ) -> Dict[str, Any]:
        """
        Generate overall channel content analysis.
        
        Args:
            videos: List of analyzed videos
            channel_data: Channel information
            openrouter: OpenRouter service instance
            
        Returns:
            Channel-level analysis
        """
        try:
            # Aggregate video insights
            successful_analyses = [v for v in videos if v.get("analysis")]
            
            if not successful_analyses:
                return {"error": "No successful video analyses to aggregate"}
            
            # Prepare channel summary data
            channel_summary = {
                "channel_name": channel_data.get("channel_name", "Unknown"),
                "total_videos": len(videos),
                "analyzed_videos": len(successful_analyses),
                "total_views": sum(v.get("view_count", 0) for v in videos),
                "total_likes": sum(v.get("like_count", 0) for v in videos),
                "common_topics": self._extract_common_topics(successful_analyses),
                "overall_sentiment": self._aggregate_sentiment(successful_analyses)
            }
            
            prompt = f"""
            Analyze this YouTube channel based on the following data:

            {json.dumps(channel_summary, indent=2)}

            Provide channel-level insights:
            1. Content strategy assessment
            2. Audience engagement patterns
            3. Content themes and consistency
            4. Channel strengths and opportunities
            5. Recommended content directions

            Format as JSON:
            {{
                "content_strategy": "Assessment of overall content strategy",
                "audience_profile": "Description of typical audience",
                "content_themes": ["theme1", "theme2"],
                "channel_strengths": ["strength1", "strength2"],
                "opportunities": ["opportunity1", "opportunity2"],
                "recommended_directions": ["direction1", "direction2"]
            }}
            """
            
            response = await openrouter.generate_completion(
                messages=[{"role": "user", "content": prompt}],
                model=settings.get_content_analyzer_model(),
                max_tokens=600,
                temperature=0.3
            )
            
            if response.get("success"):
                try:
                    analysis_data = json.loads(response["content"])
                    return {
                        **channel_summary,
                        **analysis_data,
                        "analyzed_at": datetime.now().isoformat()
                    }
                except json.JSONDecodeError:
                    pass
            
            return channel_summary
            
        except Exception as e:
            logger.error(f"Channel analysis error: {str(e)}")
            return {"error": f"Channel analysis failed: {str(e)}"}
    
    def _generate_content_insights(
        self, 
        summary: Optional[Dict[str, Any]], 
        topics: List[Dict[str, Any]], 
        sentiment: Optional[Dict[str, Any]], 
        engagement: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate actionable content insights.
        
        Args:
            summary: Content summary data
            topics: Key topics extracted
            sentiment: Sentiment analysis results
            engagement: Engagement pattern analysis
            
        Returns:
            Content insights for comment generation
        """
        insights = {
            "content_quality": summary.get("overall_quality_score", 7) if summary else 7,
            "engagement_potential": "medium",
            "comment_opportunities": [],
            "discussion_starters": [],
            "audience_interests": []
        }
        
        # Extract discussion opportunities from topics
        if topics:
            high_relevance_topics = [t for t in topics if t.get("relevance_score", 0) > 7]
            insights["discussion_starters"] = [t.get("topic", "") for t in high_relevance_topics[:3]]
            insights["audience_interests"] = [t.get("category", "") for t in topics[:5]]
        
        # Determine engagement potential from sentiment and metrics
        if sentiment and engagement:
            content_positive = sentiment.get("content_sentiment", {}).get("polarity") == "positive"
            audience_positive = sentiment.get("audience_sentiment", {}).get("polarity") == "positive"
            high_engagement = engagement.get("engagement_quality") == "high"
            
            if content_positive and audience_positive and high_engagement:
                insights["engagement_potential"] = "high"
            elif content_positive or audience_positive:
                insights["engagement_potential"] = "medium"
            else:
                insights["engagement_potential"] = "low"
        
        # Generate comment opportunities
        if summary:
            content_type = summary.get("content_style", "general")
            
            comment_opportunities = {
                "educational": ["Ask follow-up questions", "Share related experiences", "Request clarifications"],
                "entertainment": ["Express appreciation", "Share reactions", "Suggest similar content"],
                "tutorial": ["Ask about advanced techniques", "Share results", "Request additional resources"],
                "promotional": ["Ask about features", "Share use cases", "Request comparisons"]
            }
            
            insights["comment_opportunities"] = comment_opportunities.get(content_type, 
                                                                        ["Engage with content", "Ask questions", "Share thoughts"])
        
        return insights
    
    def _extract_common_topics(self, videos: List[Dict[str, Any]]) -> List[str]:
        """Extract common topics across all videos."""
        topic_frequency = {}
        
        for video in videos:
            topics = video.get("main_themes", [])
            for topic_data in topics:
                topic = topic_data.get("topic", "")
                if topic:
                    topic_frequency[topic] = topic_frequency.get(topic, 0) + 1
        
        # Return most frequent topics
        sorted_topics = sorted(topic_frequency.items(), key=lambda x: x[1], reverse=True)
        return [topic for topic, freq in sorted_topics[:5]]
    
    def _aggregate_sentiment(self, videos: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate sentiment across all videos."""
        sentiments = []
        
        for video in videos:
            sentiment = video.get("sentiment_analysis")
            if sentiment and sentiment.get("content_sentiment"):
                score = sentiment["content_sentiment"].get("score", 0)
                sentiments.append(score)
        
        if sentiments:
            avg_sentiment = sum(sentiments) / len(sentiments)
            return {
                "average_score": round(avg_sentiment, 2),
                "overall_polarity": "positive" if avg_sentiment > 0.1 else "negative" if avg_sentiment < -0.1 else "neutral"
            }
        
        return {"average_score": 0, "overall_polarity": "neutral"}
    
    def _handle_analysis_fallback(self, video: Dict[str, Any], error_message: str) -> Dict[str, Any]:
        """
        Handle analysis fallback when AI analysis fails.
        
        Args:
            video: Video data dictionary
            error_message: Error description
            
        Returns:
            Fallback analysis results
        """
        # Calculate basic metrics
        view_count = video.get("view_count", 0)
        like_count = video.get("like_count", 0)
        like_ratio = (like_count / view_count * 100) if view_count > 0 else 0
        
        # Create fallback analysis results
        fallback_analysis = {
            "content_summary": "No AI analysis available",
            "main_themes": [],
            "audience_insights": "No AI analysis available",
            "engagement_factors": [],
            "key_takeaways": [],
            "content_style": "general",
            "emotional_tone": "neutral",
            "comment_opportunities": ["No AI analysis available"],
            "overall_quality_score": 5,
            "recommended_comment_style": "engaging",
            "analysis_timestamp": datetime.now().isoformat(),
            "content_length": 0,
            "ai_model_used": "Fallback",
            "analysis_version": "1.0",
            "analysis_error": error_message,
            "status": ProcessingStatus.FAILED.value,
            "failed_at": datetime.now().isoformat(),
            "current_step": "content_analyzer",
            "progress_percentage": 60  # Keep previous progress
        }
        
        # Update video with fallback analysis
        updated_video = {
            **video,
            **fallback_analysis,
            "analysis_available": False,
            "content_length_analyzed": 0
        }
        
        return updated_video
    
    def _update_workflow_state(
        self, 
        current_state: Dict[str, Any], 
        updated_videos: List[Dict[str, Any]], 
        channel_analysis: Dict[str, Any],
        successful_analyses: int, 
        failed_analyses: int
    ) -> Dict[str, Any]:
        """
        Update workflow state with analysis results.
        
        Args:
            current_state: Current workflow state
            updated_videos: Videos with analysis data
            channel_analysis: Channel-level analysis
            successful_analyses: Number of successful analyses
            failed_analyses: Number of failed analyses
            
        Returns:
            Updated workflow state
        """
        total_videos = len(updated_videos)
        
        return {
            **current_state,
            
            # Updated video data
            "videos": updated_videos,
            
            # Channel analysis
            "channel_analysis": channel_analysis,
            
            # Workflow progress
            "current_step": "comment_generator",
            "completed_steps": current_state.get("completed_steps", []) + ["content_analyzer"],
            "status": ProcessingStatus.IN_PROGRESS.value,
            "progress_percentage": 80,  # 4/5 agents completed
            
            # Statistics
            "statistics": {
                **current_state.get("statistics", {}),
                "videos_analyzed": successful_analyses,
                "analysis_failures": failed_analyses,
                "analysis_success_rate": (successful_analyses / total_videos * 100) if total_videos > 0 else 0,
                "ai_analysis_completed": True
            },
            
            # Timestamps
            "content_analyzer_completed_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat()
        }
    
    def _create_error_state(self, current_state: Dict[str, Any], error_message: str) -> Dict[str, Any]:
        """
        Create error state when content analysis fails.
        
        Args:
            current_state: Current workflow state
            error_message: Error description
            
        Returns:
            Error state
        """
        return {
            **current_state,
            "status": ProcessingStatus.FAILED.value,
            "error_message": f"Content analysis failed: {error_message}",
            "failed_at": datetime.now().isoformat(),
            "current_step": "content_analyzer",
            "progress_percentage": 60  # Keep previous progress
        }


# Agent node function for LangGraph integration
async def content_analyzer_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node function for Content Analyzer Agent.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated workflow state with AI analysis
    """
    agent = ContentAnalyzerAgent()
    return await agent.execute(state)


# Helper functions for testing and development
async def test_content_analyzer(sample_video_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Test function for Content Analyzer Agent.
    
    Args:
        sample_video_data: Sample video data for testing
        
    Returns:
        Test result state
    """
    initial_state = {
        "videos": [sample_video_data],
        "channel_data": {
            "channel_name": "Test Channel",
            "subscriber_count": 10000
        },
                    "completed_steps": ["channel_parser", "description_extractor", "content_scraper"],
        "statistics": {}
    }
    
    agent = ContentAnalyzerAgent()
    result = await agent.execute(initial_state)
    
    return result


# Export the main components
__all__ = [
    'ContentAnalyzerAgent',
    'content_analyzer_node',
    'test_content_analyzer'
] 