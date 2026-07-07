from Backend.app.services.documents import normalize_text
import pytest

# TEST NORMALIZE_TEXT:

class TestWhiteSpaceCollapse: 
    
    def test_multiple_spaces_collapsed(self):
        assert normalize_text("a       b") == "a b"
        
    def test_tabs_collapsed(self):
        assert normalize_text("a\t\tb") == "a b"
    
    def test_mixed_spaces_and_taps(self):
        assert normalize_text("a\t  b\tc") == "a b c"
    
    def test_single_space_unchanged(self):
        assert normalize_text("a b") == "a b"
    
    def test_newlines_not_collapsed(self):
        assert normalize_text("a\nb") == "a\nb"

class TestHyphenatedLineBreaks: 
    
    def test_hyphen_break_joins_word(self):
        assert normalize_text("hyp-\nhenated") == "hyphenated"
    
    def test_hyphen_break_with_digits(self):
        assert normalize_text("end-\n123") == "end123"
    
    def test_hyphen_not_joint_without_newline(self):
        assert normalize_text("end-123") == "end-123"
        
    def test_multiple_hyphen_breaks(self):
        assert normalize_text("multi-\npart word-\nbreak") == "multipart wordbreak"
    
    def test_hyphen_break_with_non_word_after_not_joined(self):
        assert normalize_text("end-\n!oops") == "end-\n!oops"
        
class TestExcessiveNewlines:
    def test_three_newlines_collapsed_to_two(self):
        assert normalize_text("a\n\n\nb") == "a\n\nb"

    def test_many_newlines_collapsed_to_two(self):
        assert normalize_text("a\n\n\n\n\n\nb") == "a\n\nb"

    def test_two_newlines_unchanged(self):
        assert normalize_text("a\n\nb") == "a\n\nb"

    def test_single_newline_unchanged(self):
        assert normalize_text("a\nb") == "a\nb"


class TestStripping:
    def test_leading_trailing_whitespace_stripped(self):
        assert normalize_text("   hello   ") == "hello"

    def test_leading_trailing_newlines_stripped(self):
        assert normalize_text("\n\n\nhello\n\n\n") == "hello"

    def test_leading_trailing_mixed_whitespace_stripped(self):
        assert normalize_text("  \n\t hello \t\n  ") == "hello"


class TestEdgeCases:
    def test_empty_string(self):
        assert normalize_text("") == ""

    def test_whitespace_only_string(self):
        assert normalize_text("   \n\n\n   ") == ""

    def test_no_changes_needed(self):
        assert normalize_text("Hello world") == "Hello world"

    def test_combination_of_all_rules(self):
        text = "  This   is  a\ttest-\nsentence.\n\n\n\nSecond   paragraph.  "
        expected = "This is a testsentence.\n\nSecond paragraph."
        assert normalize_text(text) == expected
        
    

# TEST CHUNKER



    