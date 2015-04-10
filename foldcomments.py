from sublime import Region, Settings, load_settings
import sublime_plugin

from itertools import tee, chain

try:
    from itertools import izip as zip
except ImportError: # will be 3.x series
    pass

def previous_and_current(iterable, *iterables):
    """
    Includes the previous value of iterable in iteration

    > previous_and_current([1,2,3])
    => (None, 1)
    => (1, 2)
    => (2, 3)
    """
    prevs, items = tee(iterable, 2)
    # Offset for the first element, since has no previous value
    prevs = chain([None], prevs)
    return zip(prevs, items, *iterables)

def is_comment_multi_line(view, region):
    return len(view.lines(region)) > 1

def normalize_comment(view, region):
    if is_comment_multi_line(view, region):
        return normalize_multiline_comment(view, region)
    else:
        return normalize_singleline_comment(view, region)


def normalize_singleline_comment(view, region):
    """
    Since single line comments include the newline
    if we don't explicitly make sure newline is kept
    out of the fold indicator, it will munge together
    with code. Example:

    // This is an example comment
    function foo() {

    Becomes:

    (..) function foo() {

    When what we really want is to keep the fold
    on it's own line, like so:

    (..)
    function foo() {
    """
    region_str = view.substr(region)
    last_newline = region_str.rfind('\n')

    if (last_newline == -1):
        # Single-line block comments don't include
        # their newline.
        # /* foo bar baz */ <-- like this
        return region
    else:
        return Region(region.begin(), region.begin() + last_newline)


def normalize_multiline_comment(view, region):
    """
    This is needed since in some languages it seems
    the boundaries for proper block-comments
    and chained single-line comments differ. The
    chaines single-line comments have the last point
    ( .end() .b etc) of their region set to the subsequent line,
    while the block comments have it set to the last char
    of their last line.

    Example where the @ char signifies
    the last endpoint:

    BLOCK COMMENT

    /**
     * This is an example comment
     */@ <---
    function foobar() {

    MULTIPLE SINGLE COMMENTS

    //
    // This is an example comment
    //
    @function foobar() { <---

    What we do to fix this is not to use the boundaries
    for the regions, but instead use the last line
    for the region - which seems to have the correct end
    point set.
    """
    lines = view.lines(region)
    last_line = lines[-1]
    last_point = last_line.b
    return Region(region.a, last_point)


class CommentNodes:

    def __init__(self, view):
        self.comments = None # collection of Region objects
        self.settings = load_settings("foldcomments.sublime-settings")
        self.view = view
        self.find_comments()
        self.apply_settings()

    def find_comments(self):
        self.comments = [
            normalize_comment(self.view, c) for c in self.view.find_by_selector('comment')
        ]

    def apply_settings(self):
        if not self.settings.get('fold_single_line_comments'):
            self.remove_single_line_comments()

        if self.settings.get('concatenate_adjacent_comments'):
            self.concatenate_adjacent_comments()

    def remove_single_line_comments(self):
        self.comments = [c for c in self.comments if is_comment_multi_line(self.view, c)]

    def concatenate_adjacent_comments(self):
        """
        Merges any comments that are adjacent.
        """

        def concatenate(region1, region2):
            return region1.cover(region2)

        def is_adjacent(region1, region2):
            region_inbetween = Region(region1.end(), region2.begin())
            return len(self.view.substr(region_inbetween).strip()) == 0

        concatenated_comments = []

        for prev_comment, comment in previous_and_current(self.comments):
            concatenated_comment = None

            # prev wont be set on first iteration
            if prev_comment and is_adjacent(prev_comment, comment):
                concatenated_comment = concatenate(concatenated_comments.pop(), comment)

            concatenated_comments.append(concatenated_comment or comment)

        self.comments = concatenated_comments

    def fold(self):
        self.view.fold(self.comments)

    def unfold(self):
        self.view.unfold(self.comments)

    def toggle_folding(self):
        def is_folded(comments):
            return self.view.unfold(comments[0])  # False if /already folded/

        self.unfold() if is_folded(self.comments) else self.fold()


# ================================= COMMANDS ==================================

class ToggleFoldCommentsCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        comments = CommentNodes(self.view)
        comments.toggle_folding()


class FoldCommentsCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        comments = CommentNodes(self.view)
        comments.fold()


class UnfoldCommentsCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        comments = CommentNodes(self.view)
        comments.unfold()
