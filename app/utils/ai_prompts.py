"""
Advanced AI Prompting System

This module contains sophisticated prompts, role definitions, and context management
for all AI agents in the YouTube comment automation system. It implements best practices
in prompt engineering, psychological understanding, and strategic communication.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime


class AIPromptManager:
    """Centralized manager for AI prompts with advanced strategies."""
    
    def __init__(self):
        """Initialize the prompt manager with role definitions and strategies."""
        self.role_definitions = self._initialize_role_definitions()
        self.prompt_strategies = self._initialize_prompt_strategies()
        self.context_frameworks = self._initialize_context_frameworks()
    
    def _initialize_role_definitions(self) -> Dict[str, Dict[str, str]]:
        """Define expert roles for different AI tasks."""
        return {
            "content_analyst": {
                "expertise": "Senior digital content strategist and audience psychology expert",
                "background": "Deep expertise in YouTube ecosystem analysis, content strategy, and audience engagement patterns",
                "capabilities": "Comprehensive content analysis, strategic insights, audience psychology assessment",
                "perspective": "Strategic and analytical with focus on actionable insights"
            },
            "comment_creator": {
                "expertise": "Master of digital communication and audience engagement psychology",
                "background": "Expert in crafting authentic, engaging comments that build communities and drive discussions",
                "capabilities": "Psychological engagement strategies, authentic voice creation, community building",
                "perspective": "Authentic and community-focused with emphasis on genuine value addition"
            },
            "content_strategist": {
                "expertise": "YouTube content strategist with viral content creation experience",
                "background": "Expertise in audience development, content planning, and trend analysis",
                "capabilities": "Strategic content planning, trend identification, audience growth strategies",
                "perspective": "Growth-oriented and trend-aware with focus on scalable content strategies"
            },
            "sentiment_analyst": {
                "expertise": "Expert in sentiment analysis, emotional intelligence, and audience psychology",
                "background": "Advanced understanding of emotional landscapes in digital communication",
                "capabilities": "Nuanced sentiment analysis, emotional intelligence assessment, community psychology",
                "perspective": "Emotionally intelligent and psychologically informed"
            }
        }
    
    def _initialize_prompt_strategies(self) -> Dict[str, Dict[str, Any]]:
        """Define advanced prompting strategies."""
        return {
            "chain_of_thought": {
                "description": "Step-by-step reasoning for complex analysis",
                "structure": "Problem → Analysis Steps → Reasoning → Conclusion",
                "use_cases": ["content_analysis", "sentiment_analysis", "strategic_planning"]
            },
            "role_playing": {
                "description": "Embodying expert personas for specialized tasks",
                "structure": "Role Definition → Context → Task → Guidelines → Output",
                "use_cases": ["comment_generation", "content_strategy", "audience_analysis"]
            },
            "few_shot_learning": {
                "description": "Learning from examples for consistent output",
                "structure": "Examples → Pattern Recognition → Application → Generation",
                "use_cases": ["comment_styles", "content_categorization", "quality_assessment"]
            },
            "constraint_based": {
                "description": "Working within specific parameters and limitations",
                "structure": "Constraints → Objectives → Strategy → Implementation",
                "use_cases": ["comment_length", "community_guidelines", "brand_voice"]
            },
            "multi_perspective": {
                "description": "Analyzing from multiple viewpoints",
                "structure": "Perspective 1 → Perspective 2 → Synthesis → Insights",
                "use_cases": ["audience_analysis", "content_optimization", "engagement_strategy"]
            }
        }
    
    def _initialize_context_frameworks(self) -> Dict[str, Dict[str, Any]]:
        """Define context frameworks for different analysis types."""
        return {
            "content_analysis": {
                "dimensions": [
                    "content_strategy", "audience_psychology", "engagement_optimization",
                    "competitive_positioning", "quality_assessment", "trend_alignment"
                ],
                "metrics": ["relevance", "value", "engagement_potential", "authenticity"],
                "outputs": ["strategic_insights", "optimization_recommendations", "audience_insights"]
            },
            "comment_generation": {
                "dimensions": [
                    "audience_psychology", "engagement_triggers", "authenticity_factors",
                    "community_building", "value_addition", "discussion_catalysts"
                ],
                "metrics": ["engagement_potential", "authenticity", "value_addition", "community_fit"],
                "outputs": ["comment_text", "engagement_strategy", "community_impact"]
            },
            "sentiment_analysis": {
                "dimensions": [
                    "emotional_intelligence", "community_psychology", "engagement_quality",
                    "authenticity_assessment", "relationship_dynamics", "cultural_context"
                ],
                "metrics": ["emotional_accuracy", "nuance_level", "cultural_sensitivity", "actionability"],
                "outputs": ["sentiment_profile", "emotional_insights", "engagement_recommendations"]
            }
        }
    
    def generate_content_analysis_prompt(
        self, 
        content: str, 
        metrics: Dict[str, Any], 
        context: Dict[str, Any] = None
    ) -> str:
        """Generate enhanced content analysis prompt."""
        role = self.role_definitions["content_analyst"]
        framework = self.context_frameworks["content_analysis"]
        
        context_section = ""
        if context:
            context_section = f"""
ADDITIONAL CONTEXT:
- Channel Type: {context.get('channel_type', 'Unknown')}
- Target Audience: {context.get('target_audience', 'General')}
- Content Category: {context.get('content_category', 'General')}
- Analysis Purpose: {context.get('analysis_purpose', 'General analysis')}
"""
        
        return f"""You are a {role['expertise']} with {role['background']}. Your {role['capabilities']} enable you to provide {role['perspective']} analysis.

CONTENT TO ANALYZE:
{content}

PERFORMANCE METRICS:
- Views: {metrics.get('view_count', 0):,}
- Likes: {metrics.get('like_count', 0):,}
- Comments: {metrics.get('comment_count', 0):,}
- Engagement Rate: {self._calculate_engagement_rate(metrics):.2f}%
{context_section}

STRATEGIC ANALYSIS FRAMEWORK:
Analyze through these critical dimensions:

1. CONTENT STRATEGY ASSESSMENT:
   - Value proposition and unique positioning
   - Competitive differentiation factors
   - Scalability and series potential
   - Brand alignment and consistency

2. AUDIENCE PSYCHOLOGY ANALYSIS:
   - Primary motivations and pain points
   - Emotional engagement drivers
   - Knowledge level and preferences
   - Community building potential

3. ENGAGEMENT OPTIMIZATION:
   - Hook effectiveness and retention
   - Discussion catalyst elements
   - Shareability and viral factors
   - Call-to-action opportunities

4. QUALITY & AUTHENTICITY:
   - Information value and accuracy
   - Production quality indicators
   - Authenticity and credibility
   - Educational/entertainment balance

ANALYSIS METHODOLOGY:
Apply chain-of-thought reasoning:
1. Initial content assessment
2. Audience alignment evaluation
3. Engagement factor identification
4. Strategic positioning analysis
5. Optimization opportunity recognition
6. Synthesis and recommendations

OUTPUT REQUIREMENTS (JSON format):
{{
    "strategic_analysis": {{
        "content_positioning": "Market positioning and competitive context",
        "unique_value_proposition": "Distinctive value delivered to audience",
        "competitive_advantages": ["strength1", "strength2", "strength3"],
        "scalability_assessment": "Growth and series potential evaluation",
        "brand_consistency": "Alignment with channel/creator brand"
    }},
    "audience_insights": {{
        "primary_demographics": "Target audience profile",
        "psychological_drivers": ["motivation1", "motivation2", "motivation3"],
        "engagement_preferences": "Preferred interaction styles",
        "knowledge_level": "beginner/intermediate/advanced/mixed",
        "community_potential": "Community building likelihood and strategy"
    }},
    "engagement_optimization": {{
        "hook_effectiveness": "Opening engagement assessment",
        "retention_factors": ["element1", "element2", "element3"],
        "discussion_catalysts": ["catalyst1", "catalyst2", "catalyst3"],
        "shareability_factors": ["factor1", "factor2", "factor3"],
        "improvement_opportunities": ["opportunity1", "opportunity2"]
    }},
    "content_quality": {{
        "information_value": 8.5,
        "production_quality": 7.8,
        "authenticity_score": 9.2,
        "educational_value": 8.0,
        "entertainment_value": 7.5,
        "overall_quality": 8.2
    }},
    "themes": ["Primary theme", "Secondary theme", "Supporting theme"],
    "summary": "Comprehensive strategic summary",
    "key_takeaways": ["Actionable insight 1", "Actionable insight 2"],
    "discussion_points": ["Discussion starter 1", "Discussion starter 2"],
    "strategic_recommendations": ["Recommendation 1", "Recommendation 2"]
}}

QUALITY STANDARDS:
✅ Provide insights that are strategically actionable, psychologically informed, competitively aware, and evidence-based
❌ Avoid generic observations, unsupported claims, or template responses

Focus on delivering strategic intelligence that transforms content understanding into actionable growth strategies."""
    
    def generate_comment_creation_prompt(
        self,
        video_context: Dict[str, Any],
        analysis_data: Dict[str, Any],
        style: str = "engaging"
    ) -> str:
        """Generate enhanced comment creation prompt."""
        role = self.role_definitions["comment_creator"]
        
        style_strategies = {
            "engaging": {
                "psychology": "Leverage curiosity, social proof, and community building",
                "approach": "Create intrigue and encourage discussion through questions and insights",
                "tone": "Enthusiastic but authentic, conversational and inclusive",
                "triggers": ["curiosity", "social_connection", "value_recognition"]
            },
            "thoughtful": {
                "psychology": "Appeal to intellectual curiosity and expertise recognition",
                "approach": "Provide analytical depth and meaningful observations",
                "tone": "Reflective and insightful, demonstrating careful consideration",
                "triggers": ["intellectual_stimulation", "expertise_validation", "depth_appreciation"]
            },
            "casual": {
                "psychology": "Build relatability and social connection",
                "approach": "Sound like a friend sharing genuine reactions",
                "tone": "Natural and relaxed, using everyday language",
                "triggers": ["relatability", "friendship", "shared_experience"]
            },
            "professional": {
                "psychology": "Establish credibility and thought leadership",
                "approach": "Demonstrate expertise while adding constructive value",
                "tone": "Knowledgeable and authoritative yet approachable",
                "triggers": ["credibility", "expertise", "professional_value"]
            }
        }
        
        strategy = style_strategies.get(style, style_strategies["engaging"])
        
        return f"""You are a {role['expertise']} with {role['background']}. Your {role['capabilities']} enable you to create comments with {role['perspective']}.

VIDEO CONTEXT:
Title: "{video_context.get('title', '')}"
Channel: {video_context.get('channel', '')}
Performance: {video_context.get('views', 0):,} views, {video_context.get('likes', 0):,} likes

CONTENT INTELLIGENCE:
Summary: {analysis_data.get('summary', '')}
Key Themes: {', '.join(analysis_data.get('themes', []))}
Audience Profile: {analysis_data.get('audience_insights', {}).get('primary_demographics', 'General audience')}
Engagement Hooks: {', '.join(analysis_data.get('engagement_optimization', {}).get('hook_effectiveness', [])[:3])}

COMMENT STRATEGY:
Style: {style.title()}
Psychology: {strategy['psychology']}
Approach: {strategy['approach']}
Tone: {strategy['tone']}
Triggers: {', '.join(strategy['triggers'])}

ENGAGEMENT PSYCHOLOGY FRAMEWORK:
Apply these proven psychological principles:

1. RECIPROCITY: Acknowledge creator's effort or expertise
2. SOCIAL PROOF: Reference community or shared experiences  
3. CURIOSITY GAP: Ask questions that others want answered
4. VALUE ADDITION: Share insights that enhance discussion
5. AUTHENTICITY: Sound genuine and personally invested
6. SPECIFICITY: Reference particular content elements

COMMENT CRAFTING METHODOLOGY:
1. HOOK: Open with attention-capturing element
2. VALUE: Add insight, question, or observation
3. CONNECTION: Link to broader themes or audience interests
4. CATALYST: Include discussion-encouraging element

OPTIMIZATION TARGETS:
- Length: 50-200 characters (optimal for engagement)
- Authenticity: Sound genuinely human and invested
- Value: Add meaningful contribution to discussion
- Engagement: Encourage responses and community interaction

QUALITY REQUIREMENTS:
✅ Create comments that spark meaningful discussions, demonstrate genuine engagement, add authentic value, and build community connections
❌ Avoid generic praise, self-promotion, controversial content, or artificial language

Generate a single, strategically crafted comment that exemplifies authentic engagement and community building:"""
    
    def generate_sentiment_analysis_prompt(
        self,
        content: str,
        metrics: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> str:
        """Generate enhanced sentiment analysis prompt."""
        role = self.role_definitions["sentiment_analyst"]
        
        return f"""You are an {role['expertise']} with {role['background']}. Your {role['capabilities']} enable you to provide {role['perspective']} analysis.

CONTENT FOR SENTIMENT ANALYSIS:
{content}

ENGAGEMENT METRICS:
- Views: {metrics.get('view_count', 0):,}
- Likes: {metrics.get('like_count', 0):,}
- Comments: {metrics.get('comment_count', 0):,}
- Like Ratio: {self._calculate_like_ratio(metrics):.2f}%

ADVANCED SENTIMENT ANALYSIS FRAMEWORK:

1. MULTI-DIMENSIONAL SENTIMENT ASSESSMENT:
   - Valence: Positive/Negative emotional direction (-1.0 to +1.0)
   - Arousal: Energy and activation level (0.0 to 1.0)
   - Dominance: Control and confidence level (0.0 to 1.0)
   - Authenticity: Genuineness perception (0.0 to 1.0)

2. EMOTIONAL INTELLIGENCE EVALUATION:
   - Primary emotions and their intensity
   - Secondary emotional undertones
   - Emotional complexity and nuance
   - Empathy and connection indicators

3. COMMUNITY PSYCHOLOGY ANALYSIS:
   - Audience engagement quality
   - Community cohesion indicators
   - Social dynamics and interaction patterns
   - Cultural and contextual factors

4. STRATEGIC SENTIMENT INSIGHTS:
   - Engagement optimization opportunities
   - Community building potential
   - Content strategy implications
   - Audience relationship dynamics

ANALYSIS METHODOLOGY:
Apply multi-perspective analysis:
1. Content creator sentiment assessment
2. Audience response sentiment evaluation
3. Community interaction dynamics
4. Cultural and contextual considerations
5. Strategic implications synthesis

OUTPUT FORMAT (JSON):
{{
    "content_sentiment": {{
        "polarity": "positive/negative/neutral",
        "confidence": 0.85,
        "valence_score": 0.7,
        "arousal_level": 0.6,
        "dominance_level": 0.8,
        "authenticity_score": 0.9,
        "emotional_complexity": "simple/moderate/complex",
        "primary_emotions": ["emotion1", "emotion2"],
        "secondary_emotions": ["emotion3", "emotion4"],
        "emotional_indicators": ["indicator1", "indicator2"]
    }},
    "audience_sentiment": {{
        "polarity": "positive/negative/neutral",
        "confidence": 0.90,
        "engagement_quality": "high/medium/low",
        "community_cohesion": 0.7,
        "satisfaction_indicators": ["indicator1", "indicator2"],
        "concern_indicators": ["concern1", "concern2"],
        "interaction_patterns": ["pattern1", "pattern2"]
    }},
    "psychological_profile": {{
        "communication_style": "direct/storytelling/instructional/entertaining",
        "personality_traits": ["trait1", "trait2", "trait3"],
        "emotional_intelligence": 0.8,
        "authenticity_indicators": ["indicator1", "indicator2"],
        "relationship_building": "strong/moderate/weak"
    }},
    "strategic_insights": {{
        "engagement_optimization": ["strategy1", "strategy2"],
        "community_building": ["approach1", "approach2"],
        "content_strategy": ["recommendation1", "recommendation2"],
        "audience_development": ["tactic1", "tactic2"]
    }},
    "sentiment_summary": "Comprehensive emotional landscape analysis"
}}

ANALYSIS STANDARDS:
✅ Provide nuanced, contextually aware, culturally sensitive, and strategically actionable insights
❌ Avoid oversimplification, bias, cultural insensitivity, or disconnected observations

Focus on emotional intelligence insights that drive authentic engagement and community building."""
    
    def _calculate_engagement_rate(self, metrics: Dict[str, Any]) -> float:
        """Calculate engagement rate from metrics."""
        views = metrics.get('view_count', 0)
        likes = metrics.get('like_count', 0)
        comments = metrics.get('comment_count', 0)
        
        if views == 0:
            return 0.0
        
        return ((likes + comments) / views) * 100
    
    def _calculate_like_ratio(self, metrics: Dict[str, Any]) -> float:
        """Calculate like ratio from metrics."""
        views = metrics.get('view_count', 0)
        likes = metrics.get('like_count', 0)
        
        if views == 0:
            return 0.0
        
        return (likes / views) * 100


# Global prompt manager instance
prompt_manager = AIPromptManager() 