from sublime import Region, Settings, load_settings
import sublime_plugin

settings = load_settings("foldcomments.sublime-settings")


def is_multi_line(view, region):
    return len(view.lines(region)) > 1


class CommentsMixin:

    def post_process_comments(self, comments):
        """ Apply settings """
        view = self.view

        if settings.get('concatenate_adjacent_comments'):
            comments = self.concatenate_adjacent_comments(comments)

        if not settings.get('fold_single_line_comments'):
            comments = self.remove_single_line_comments(comments)

        return comments

    def remove_single_line_comments(self, comments):
        return [c for c in comments if is_multi_line(self.view, c)]

    def concatenate_adjacent_comments(self, comments):
        """
        Do rudimentary stripping of comment indentation and
        appendage and then concatenate if one begins
        where another one has ended
        """
        view = self.view

        # view.line(region) strips indentations etc
        stripped_comments = list(map(view.line, comments))
        conc_comments = []

        for index, stripped_comment in enumerate(stripped_comments):
            previous_stripped_comment = stripped_comments[index - 1]

            if not previous_stripped_comment:  # first item
                conc_comments.append(comments[index])
                continue

            if previous_stripped_comment.end() + 1 == stripped_comment.begin():
                conc_comments[-1] = conc_comments[-1].cover(comments[index])
            else:
                conc_comments.append(comments[index])

        return conc_comments

    def comment_regions(self):
        view = self.view

        def normalize_multiline_comment(region):
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

        def normalize_singleline_comment(region):
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

        def normalize_regions(region):
            if is_multi_line(view, region):
                return normalize_multiline_comment(region)
            else:
                return normalize_singleline_comment(region)

        return [normalize_regions(c) for c in view.find_by_selector('comment')]


# ================================= COMMANDS ==================================


class ToggleFoldCommentsCommand(sublime_plugin.TextCommand, CommentsMixin):

    def run(self, edit):
        view = self.view
        comments = self.comment_regions()

        def is_folded(comments):
            return view.unfold(comments[0]) # False if /already folded/

        if not comments:
            return

        comments = self.post_process_comments(comments)

        if not comments:
            return

        if not is_folded(comments):
            view.fold(comments)
        else:
            view.unfold(comments)


class FoldCommentsCommand(sublime_plugin.TextCommand, CommentsMixin):

    def run(self, edit):
        view = self.view
        comments = self.comment_regions()

        if not comments:
            return

        comments = self.post_process_comments(comments)

        if not comments:
            return
        
        view.fold(comments)


class UnfoldCommentsCommand(sublime_plugin.TextCommand, CommentsMixin):

    def run(self, edit):
        view = self.view
        comments = self.comment_regions()

        if not comments:
            return

        view.unfold(comments)
