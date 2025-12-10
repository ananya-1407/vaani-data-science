"""Module to build the prompts for the talk2bill pipeline"""
import json
from typing import Dict, Any, List
from constants.talk2bill.vyapar.generic import SUPPORTED_INVOICE_CATEGORIES
from constants.talk2bill.vyapar.prompts import (
    EXPENSE_MISSING_FIELDS_PROMPT_VYP,
    EXPENSE_RULES,
    OTHER_RULES,
    EXPENSE_EXAMPLES,
    OTHER_EXAMPLES,
    INTENT_CLASSIFICATION_PROMPT_VYP,
    EXPENSE_EXTRACTION_PROMPT_V1,
    GENERIC_QUESTION_ASK_PROMPT
)


class Talk2BillPromptBuilder:
    """
    Class to build the prompts for the talk2bill pipeline
    """
    @staticmethod
    def build_all_rules_and_examples():
        """
        Build all the rules and examples for the intent classification prompt

        Returns:
            The all rules and examples
        """
        rules_list = [EXPENSE_RULES, OTHER_RULES]
        examples_list = [EXPENSE_EXAMPLES, OTHER_EXAMPLES]
        all_rules = "\n".join(rules_list)
        all_examples = "\n".join(examples_list)
        return all_rules, all_examples

    @staticmethod
    def build_intent_classification_prompt(
        history: List[Dict],
        user_query: str
    ) -> str:
        """
        Build the intent classification prompt

        Args:
            history: The history of the conversation
            user_query: The user query

        Returns:
            The intent classification prompt
        """
        all_rules, all_examples = Talk2BillPromptBuilder.build_all_rules_and_examples()
        return INTENT_CLASSIFICATION_PROMPT_VYP.format(
            all_rules=all_rules,
            all_examples=all_examples,
            history=history,
            user_query=user_query
        )

    @staticmethod
    def build_expense_extraction_prompt(
        user_input: str,
        latest_invoice: Dict[str, Any] = {},
        history: List[Dict] = []
    ) -> str:
        """
        Build the expense extraction prompt

        Args:
            user_input: The user input
            latest_invoice: The latest invoice
            history: The history of the conversation

        Returns:
            The expense extraction prompt
        """
        # Serialize the invoice to JSON string for proper formatting in the prompt
        current_invoice_json = json.dumps(
            latest_invoice,
            ensure_ascii=False
        ) if latest_invoice else "{}"
        history_json = json.dumps(history, ensure_ascii=False) if history else "[]"

        return EXPENSE_EXTRACTION_PROMPT_V1.format(
            user_input=user_input,
            current_invoice=current_invoice_json,
            history=history_json
        )

    @staticmethod
    def build_expense_missing_fields_prompt(
        extracted_data,
        user_input="",
        history: List[Dict] = []
    ) -> str:
        """
        Build the expense missing fields prompt

        Args:
            extracted_data: The extracted data
            user_input: The user input
            history: The history of the conversation

        Returns:
            The expense missing fields prompt
        """
        return EXPENSE_MISSING_FIELDS_PROMPT_VYP.format(
            extracted_data=extracted_data,
            user_input=user_input,
            history=history
        )

    @staticmethod
    def build_generic_question_ask_prompt(
        user_input: str,
        conversation_history: List[Dict]
    ) -> str:
        """
        Build the generic question ask prompt

        Args:
            user_input: The user input
            conversation_history: The history of the conversation

        Returns:
            The generic question ask prompt
        """
        return GENERIC_QUESTION_ASK_PROMPT.format(
            user_input=user_input,
            conversation_history=conversation_history,
            supported_categories=SUPPORTED_INVOICE_CATEGORIES
        )
