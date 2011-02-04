'''
mustache -- Logic-less templates.

Text outside of the delimiters ('{{' and '}}' by default) is not changed.

>>> render('sanity')
'sanity'

Variables are replaced by their value in the current context. Html special
characters are escaped inless & is used. Undefined variables are replaced with
nothing. The base context is given as the second argument, defaulting to {}.

>>> render('{{text}} {{&text}} {{nothere}}', {'text':'<>&'})
u'&lt;&gt;&amp; <>& '

Comments (!) are always ignored.

>>> render('{{!comment}}')
''

Partials (>) replace the tag with text in <file_name>.mustache. The path where
pystache looks for this file can be controlled with pystache.View, but defaults
to the cwd. The partial text is evaluated as a mustache template in the current
context.

# Requires file 'partial.mustache' in cwd
>>> render('{{>partial}}', {'a':1})
u'text in partial.mustache and a=1'

The tag delimiters may be changed using the (=) tag, where the left and right
delims are seperated by a space.

>>> render('{{=[[ ]]}} [[a]]', {'a':1})
u' 1'

Section tags (#) only include the text between them if their variable is true.

>>> render('{{#t}}I am true{{/t}} {{#f}}I am false{{/f}}',{'t':True,'f':False})
'I am true '

If a section variable is callable, it will be invoked with that section's text
and current context as argument. The section will be replaced with the value
returned by this invokation. Note: the text given to the function is not
rendered before it is passed to the callable, but the results will be rendered
afterward.

>>> render('{{#upper}}Hello {{world}}{{/upper}}',
...         {'upper':lambda x,c: x.upper(), 'world':'Earth', 'WORLD':'Mars'})
u'HELLO Mars'

Sections whose variables are iterable are repeated once for each item, with the
item as the current context. (This excludes dict like objects that have a get()
method.)

>>> people = [{'name':'Bob'},{'name':'Tom'},{'name':'Sam'}]
>>> render('{{#people}}Hello {{name}}. {{/people}}', {'people': people})
u'Hello Bob. Hello Tom. Hello Sam. '

Sections variables that are not iterable and not callables render their text once
using that variable as the current context.

>>> site = {'url':'www.x.com', 'name':'XSite'}
>>> render('{{#site}}url: {{url}}, name: {{name}}{{/site}}', {'site': site})
u'url: www.x.com, name: XSite'

Inverse sections (^) are only included if their variable is false or not defined.
These sections are never repeated and do not change the current context.

>>> base = {'t':True, 'f':False}
>>> render('{{^n}}Nodef{{/n}} {{^f}}False{{/f}} {{^t}}True{{/t}}', base)
'Nodef False '

Assertion sections (?) are only included if thier variable is true. Unlike full
sections (#), they are never repeated and they do not affect the current context.

>>> john = {'good':True, 'present':'bike'}
>>> render('{{?good}}{{present}}{{/good}}', john)
u'bike'

The current context may be addressed as {{.}}

>>> render('{{.}}', 'Current Context')
u'Current Context'

The base context may always be addressed with the period prefix. Values within
a context can be accessed using dot notation (eg a.b.c).

>>> base = {'a':1, 'cur':{'a':2}}
>>> render('{{a}} {{cur.a}} {{#cur}}{{a}} {{.a}} {{.cur.a}}{{/cur}}', base)
u'1 2 2 1 2'

Lists may be addressed using integers to specify the desired item's position just
like list indexing in Python.

>>> list = ['a','b','c']
>>> render('{{list.0}} {{list.1}} {{list.-1}}', {'list':list})
u'a b c'
'''
import re
import cgi

modifiers = {}
def modifier(symbol):
    """Decorator for associating a function with a Mustache tag modifier.

    @modifier('P')
    def render_tongue(self, tag_name=None, context=None):
        return ":P %s" % tag_name

    {{P yo }} => :P yo
    """
    def set_modifier(func):
        modifiers[symbol] = func
        return func
    return set_modifier

class Template(object):
    # The regular expression used to find a #section
    section_re = None

    # The regular expression used to find a tag.
    tag_re = None

    # Opening tag delimiter
    otag = '{{'

    # Closing tag delimiter
    ctag = '}}'

    def __init__(self, template, context=None):
        self.template = template
        self.context = context or {}
        self.compile_regexps()

    def render(self, template=None, context=None, encoding=None):
        """Turns a Mustache template into something wonderful."""
        template = template or self.template
        context = context or self.context

        template = self.render_sections(template, context)
        result = self.render_tags(template, context)
        if encoding is not None:
            result = result.encode(encoding)
        return result

    def compile_regexps(self):
        """Compiles our section and tag regular expressions."""
        tags = { 'otag': re.escape(self.otag), 'ctag': re.escape(self.ctag) }

        section = r"%(otag)s(\#|\^|\?)(.+?)%(ctag)s*(.+?)%(otag)s/\2%(ctag)s"
        self.section_re = re.compile(section % tags, re.M|re.S)

        tag = r"%(otag)s(=|&|!|>|\{)?(.+?)%(ctag)s+"
        self.tag_re = re.compile(tag % tags)

    def _get_it(self, name, context):
        '''Get item by name in current context.'''

        if name == '.':
            return context

        stack = name.split('.')
        if stack[0] == '':    
            stack = stack[1:]
            context = self.context

        for s in stack:
            if hasattr(context, 'get'):
                context = context.get(s, '')
            else:
                try:
                    context = context[int(s)]
                except:
                    return ''
           

        return context

    def render_sections(self, template, context):
        """Expands sections."""
        while 1:
            match = self.section_re.search(template)
            if match is None:
                break

            section, section_type, section_name, inner = match.group(0, 1, 2, 3)
            section_name = section_name.strip()
            it = self._get_it(section_name, context)
            replacer = ''

            if it and section_type == '#':
                if callable(it):
                    replacer = it(inner,context)
                elif hasattr(it, '__iter__') and not hasattr(it, 'get'):
                    insides = [ self.render(inner, item) for item in it ]
                    replacer = ''.join(insides)
                else:
                    replacer = self.render(inner, it)

            elif not it and section_type == '^':
                replacer = inner

            elif it and section_type == '?':
                replacer = inner

            template = template.replace(section, replacer)

        return template

    def render_tags(self, template, context):
        """Renders all the tags in a template for a context."""
        while 1:
            match = self.tag_re.search(template)
            if match is None:
                break

            tag, tag_type, tag_name = match.group(0, 1, 2)
            tag_name = tag_name.strip()
            func = modifiers[tag_type]
            replacement = func(self, tag_name, context)
            template = template.replace(tag, replacement)

        return template

    @modifier(None)
    def render_tag(self, tag_name, context):
        """Given a tag name and context, finds, escapes, and renders the tag."""
        raw = self._get_it(tag_name, context)
        if not raw and raw is not 0:
            return ''
        return cgi.escape(unicode(raw))

    @modifier('!')
    def render_comment(self, tag_name=None, context=None):
        """Rendering a comment always returns nothing."""
        return ''

    @modifier('&')
    def render_unescaped(self, tag_name=None, context=None):
        """Render a tag without escaping it."""
        return unicode(self._get_it(tag_name, context))

    @modifier('>')
    def render_partial(self, tag_name=None, context=None):
        """Renders a partial within the current context."""
        # Import view here to avoid import loop
        try:
            from pystache.view import View
        except ImportError:
            from view import View

        view = View(context=self.context)
        view.template_name = tag_name

        return view.render(context=context)

    @modifier('=')
    def render_delimiter(self, tag_name=None, context=None):
        """Changes the Mustache delimiter."""
        self.otag, self.ctag = tag_name.split(' ')
        self.compile_regexps()
        return ''

def render(template=None, context=None, encoding=None):
    '''Render a mustache template.

    >>> render('my {{object}}', {'object':'friend'}, 'utf-8')
    'my friend'
    '''
    context = context and context.copy() or None
    return Template(template, context).render(encoding=encoding)

if __name__ == '__main__':
    import doctest
    doctest.testmod()