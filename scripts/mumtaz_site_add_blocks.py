# Run inside `odoo shell` (env is provided). Adds the localisation, pricing and
# FAQ blocks to an existing Mumtaz preview page: the page record is noupdate,
# so a module upgrade alone does not change it. Blocks already present are
# left untouched; nothing else on the page is modified.
from lxml import etree
from lxml import html as lhtml

page = env.ref('mumtaz_website_builder.page_mumtaz_preview')
view = page.view_id
root = etree.fromstring(view.arch_db.encode())
wrap = root.xpath("//*[@id='wrap']")[0]
have = {s.get('data-snippet') for s in wrap.xpath(".//section[@data-snippet]")}


def block(key):
    # QWeb renders HTML (bare ampersands and the like): parse it as HTML, then
    # the element joins the XML arch and is re-serialised safely by etree
    html = env['ir.qweb']._render('mumtaz_website_builder.%s' % key)
    return lhtml.fragment_fromstring(str(html).strip())


def insert(key, before=None, after=None):
    if key in have:
        return
    el = block(key)
    ref = wrap.xpath(".//section[@data-snippet='%s']" % (before or after))
    if not ref:
        wrap.append(el)
    elif before:
        ref[0].addprevious(el)
    else:
        ref[0].addnext(el)
    have.add(key)


insert('s_mumtaz_localisation', after='s_mumtaz_editions')
insert('s_mumtaz_pricing', before='s_mumtaz_contact')
insert('s_mumtaz_faq', before='s_mumtaz_contact')
view.write({'arch_db': etree.tostring(root, encoding='unicode')})
env.cr.commit()
print('sections now:', [s.get('data-snippet') for s in wrap.xpath(".//section[@data-snippet]")])
