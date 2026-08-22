import os
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq


class JudgeScore(BaseModel):
    score: float = Field(
        description="Semantic similarity score between 0.0 and 1.0 (1.0 for perfect match, 0.5 for partial, 0.0 for wrong).",
        ge=0.0,
        le=1.0,
    )
    justification: str = Field(
        description="Brief justification explaining the assigned evaluation score."
    )


def evaluate_hypothesis(hypothesis: str, ground_truth: str) -> JudgeScore:
    """
    Evaluates an agent's root cause hypothesis against the ground truth using an LLM-as-a-judge.
    Returns a structured JudgeScore containing a float score (0.0-1.0) and justification.
    """
    api_key = os.getenv("GROQ_API_KEY")

    llm = ChatGroq(
        api_key=api_key,
        model="openai/gpt-oss-20b",
        temperature=0.1,
    )

    structured_llm = llm.with_structured_output(JudgeScore)

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are an expert SRE Judge. Compare the agent's root cause hypothesis against the ground truth. "
            "Score 1.0 for a perfect semantic match, 0.5 for partial, 0.0 for wrong. Provide a brief justification."
        ),
        (
            "user",
            "Agent Hypothesis:\n{hypothesis}\n\n"
            "Ground Truth Root Cause:\n{ground_truth}\n\n"
            "Evaluate semantic alignment and return the score and justification."
        ),
    ])

    chain = prompt | structured_llm

    try:
        score_obj: JudgeScore = chain.invoke({
            "hypothesis": hypothesis or "No hypothesis provided",
            "ground_truth": ground_truth or "No ground truth provided",
        })
        return score_obj
    except Exception as e:
        print(f"Error invoking SRE Judge LLM: {e}")
        # Deterministic fallback evaluation if API rate-limits or fails
        hyp_lower = (hypothesis or "").lower()
        gt_lower = (ground_truth or "").lower()

        common_words = set(hyp_lower.split()) & set(gt_lower.split())
        stopwords = {"a", "an", "the", "in", "on", "of", "and", "is", "to", "for", "service", "cause", "in", "at"}
        meaningful_common = common_words - stopwords

        if len(meaningful_common) >= 3:
            return JudgeScore(
                score=1.0,
                justification=f"Fallback evaluation: strong semantic keyword overlap ({', '.join(meaningful_common)}).",
            )
        elif len(meaningful_common) >= 1:
            return JudgeScore(
                score=0.5,
                justification=f"Fallback evaluation: partial semantic keyword overlap ({', '.join(meaningful_common)}).",
            )
        else:
            return JudgeScore(
                score=0.0,
                justification="Fallback evaluation: minimal semantic overlap between hypothesis and ground truth.",
            )
