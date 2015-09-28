# -*- coding: utf-8 -*-
import ast
from abc import ABCMeta
from sqlalchemy import desc, func
from flask.ext.babel import gettext as _
from oec import db, db_data, available_years, earliest_data
from oec.utils import num_format
from oec.db_attr import models as attrs
from oec.visualize.models import Build

class Profile(object):

    __metaclass__ = ABCMeta

    def __init__(self, classification, id):
        self.classification = classification
        self.models = getattr(db_data, "{}_models".format(self.classification))
        self.id = id
        self.year = available_years[self.classification][-1]

    def title(self):
        return self.attr.get_attr_name()

    def palette(self):
        if hasattr(self.attr, "palette"):
            p = self.attr.palette
        else:
            p = None
        if p:
            return ast.literal_eval(p)
        else:
            return []

    @staticmethod
    def stringify_items(items, val=None, attr=None):
        str_items = []
        for i in items:
            if attr:
                this_attr = getattr(i, attr)
            else:
                this_attr = i
            if val:
                str_item = u"<a href='{}'>{}</a> ({})".format(this_attr.get_profile_url(), this_attr.get_name(), num_format(getattr(i, val), "export_val"))
            else:
                str_item = u"<a href='{}'>{}</a>".format(this_attr.get_profile_url(), this_attr.get_name())
            str_items.append(str_item)
        if len(items) > 1:
            str_items = u"{0} {1} {2}".format(", ".join(str_items[:-1]), _("and"), str_items[-1])
        else:
            str_items = str_items[0]
        return str_items


class Country(Profile):

    def __init__(self, classification, id):
        super(Country, self).__init__(classification, id)
        self.attr = attrs.Country.query.filter_by(id_3char = self.id).first()
        self.cached_stats = []

    def stats(self):
        if not self.cached_stats:
            sitc_swaps = {"eublx":"eubel"}
            if self.attr.id in sitc_swaps:
                attr = attrs.Country.query.get(sitc_swaps[self.attr.id])
            else:
                attr = self.attr
            start_year = earliest_data.get(attr.id, 1980)
            all_stats = [("eci", _('Econ Complexity')), ("export_val", _('Exports')), ("import_val", _('Imports')), ("gdp_pc_current_ppp", _('GDP Per Capita'))]
            for s, s_title in all_stats:
                if "val" in s:
                    yo_historic = db_data.sitc_models.Yo.query.filter_by(country=attr).filter(db_data.sitc_models.Yo.year >= start_year).all()
                    # raise Exception([x.export_val for x in yo_historic])
                    yo_base_q = self.models.Yo.query.filter_by(year=self.year)
                    this_yo = yo_base_q.filter_by(country=attr).first()
                else:
                    start_year = 1990 if "gdp" in s else start_year
                    yo_historic = attrs.Yo.query.filter_by(country=attr).filter(attrs.Yo.year >= start_year).all()
                    # raise Exception([x.population for x in yo_historic])
                    yo_base_q = attrs.Yo.query.filter_by(year=self.year)
                    this_yo = yo_base_q.filter_by(country=attr).first()

                res = yo_base_q.order_by(desc(s)).all()
                val = getattr(this_yo, s, None)
                if val:
                    my_stat = {"key":s, "rank":res.index(this_yo)+1, "total":len(res), "title":s_title, \
                                "val":val, "sparkline":{
                                    "start": start_year, "end": available_years["sitc"][-1], \
                                    "val": [float(getattr(yh, s)) if getattr(yh, s) is not None else 0 for yh in yo_historic]
                                }
                              }
                    self.cached_stats.append(my_stat)
        return self.cached_stats

    def intro(self):
        all_paragraphs = []
        ''' Paragraph #1
        '''
        this_yo = self.models.Yo.query.filter_by(year = self.year, country = self.attr).first()
        all_yo = self.models.Yo.query.filter_by(year = self.year).order_by(desc("export_val")).all()
        if this_yo:
            p1 = []
            econ_rank = num_format(all_yo.index(this_yo) + 1, "ordinal") if all_yo.index(this_yo) else ""
            export_val = this_yo.export_val
            import_val = this_yo.import_val
            trade_balance = u"positive" if export_val > import_val else u"negative"
            trade_delta = abs(export_val - import_val)
            this_attr_yo = attrs.Yo.query.filter_by(year = self.year, country = self.attr).first()
            # eci_rank = this_attr_yo.eci_rank
            formatted_vals = {"export_val":export_val, "import_val":import_val, "trade_delta":trade_delta}
            formatted_vals = {k: num_format(v) for k, v in formatted_vals.items()}
            p1.append(_(u"%(country)s is the %(econ_rank)s largest export economy in the world",
                        country=self.attr.get_name(article=True), econ_rank=econ_rank))
            if this_attr_yo and this_attr_yo.eci_rank:
                eci_rank = num_format(this_attr_yo.eci_rank, "ordinal") if this_attr_yo.eci_rank > 1 else ""
                p1.append(_(" and the %(eci_rank)s most complex economy according to the Economic Complexity Index (ECI). ", eci_rank=eci_rank))
            else:
                p1.append(". ")
            p1.append(_(u"In %(year)s, %(country)s exported $%(export_val)s and imported $%(import_val)s, resulting in a %(positive_negative)s trade balance of $%(trade_delta)s. ",
                        year=self.year, country=self.attr.get_name(article=True), export_val=formatted_vals["export_val"], import_val=formatted_vals["import_val"], positive_negative=trade_balance, trade_delta=formatted_vals["trade_delta"]))
            if this_attr_yo:
                gdp = this_attr_yo.gdp
                gdp_pc = this_attr_yo.gdp_pc_current
                formatted_vals = {"gdp":gdp, "gdp_pc":gdp_pc}
                formatted_vals = {k: num_format(v) for k, v in formatted_vals.items()}
                p1.append(_(u"In %(year)s the GDP of %(country)s was $%(gdp)s and its GDP per capita was $%(gdp_pc)s.",
                            year=self.year, country=self.attr.get_name(article=True), gdp=formatted_vals['gdp'], gdp_pc=formatted_vals['gdp_pc']))
            all_paragraphs.append("".join(p1))

        ''' Paragraph #2
        '''
        yop_exp = self.models.Yop.query.filter_by(year = self.year, origin = self.attr, hs92_id_len=6).order_by(desc("export_val")).limit(5).all()
        if yop_exp:
            exports_list = self.stringify_items(yop_exp, "export_val", "product")
            yop_imp = self.models.Yop.query.filter_by(year = self.year, origin = self.attr, hs92_id_len=6).order_by(desc("import_val")).limit(5).all()
            imports_list = self.stringify_items(yop_imp, "import_val", "product")
            p2 = _(u"The top exports of %(country)s are %(exports_list)s, using the 1992 revision of the HS (Harmonized System) classification. Its top imports are %(imports_list)s.", country=self.attr.get_name(article=True), exports_list=exports_list, imports_list=imports_list)
            all_paragraphs.append(p2)

        ''' Paragraph #3
        '''
        yod_exp = self.models.Yod.query.filter_by(year = self.year, origin = self.attr).order_by(desc("export_val")).limit(5).all()
        if yod_exp:
            dest_list = self.stringify_items(yod_exp, "export_val", "dest")
            yod_imp = self.models.Yod.query.filter_by(year = self.year, dest = self.attr).order_by(desc("import_val")).limit(5).all()
            origin_list = self.stringify_items(yod_imp, "import_val", "origin")
            p3 = _(u"The top export destinations of %(country)s are %(destinations)s. The top import origins are %(origins)s.", country=self.attr.get_name(article=True), destinations=dest_list, origins=origin_list)
            all_paragraphs.append(p3)

        ''' Paragraph #4
        '''
        land_borders = self.attr.borders()
        maritime_borders = self.attr.borders(maritime=True)
        if maritime_borders or land_borders:
            if maritime_borders and not land_borders:
                p4 = _(u"%(country)s is an island and borders %(maritime_borders)s by sea.", country=self.attr.get_name(article=True), maritime_borders=self.stringify_items(maritime_borders))
            if not maritime_borders and land_borders:
                p4 = _(u"%(country)s borders %(land_borders)s.", country=self.attr.get_name(article=True), land_borders=self.stringify_items(land_borders))
            if maritime_borders and land_borders:
                p4 = _(u"%(country)s borders %(land_borders)s by land and %(maritime_borders)s by sea.", country=self.attr.get_name(article=True), land_borders=self.stringify_items(land_borders), maritime_borders=self.stringify_items(maritime_borders))
            all_paragraphs.append(p4)

        return all_paragraphs

    def sections(self):
        sections = []
        ''' Trade Section
        '''
        export_subtitle, import_subtitle, dest_subtitle, origin_subtitle = [None]*4

        export_tmap = Build("tree_map", "hs92", "export", self.attr, "all", "show", self.year)
        import_tmap = Build("tree_map", "hs92", "import", self.attr, "all", "show", self.year)

        yop_base = self.models.Yop.query.filter_by(year = self.year, origin = self.attr, hs92_id_len=6)
        # get growth
        past_yr = self.year - 5
        past_yo = self.models.Yo.query.filter_by(year = past_yr, country = self.attr).first()
        this_yo = self.models.Yo.query.filter_by(year = self.year, country = self.attr).first()
        exp_val_stat = filter(lambda s: s["key"] == "export_val", self.stats())
        if exp_val_stat:
            exp_val_stat = exp_val_stat.pop()
            exp_rank = num_format(exp_val_stat["rank"], "ordinal") if exp_val_stat["rank"] > 1 else ""
            export_subtitle = _(u"In %(year)s %(country)s exported $%(export_val)s, making it the %(export_rank)s largest exporter in the world. ",
                                year=self.year, country=self.attr.get_name(article=True), export_val=num_format(exp_val_stat["val"]), export_rank=exp_rank)
            if past_yo:
                chg = "increased" if this_yo.export_val_growth_pct_5 >= 0 else "decreased"
                export_subtitle += _(u"During the last five years the exports of %(country)s have %(increased_decreased)s at an annualized rate of %(change_rate)s%%, from $%(past_export_val)s in %(past_year)s to $%(current_export_val)s in %(current_year)s. ",
                                        country=self.attr.get_name(article=True), increased_decreased=chg, change_rate=num_format(this_yo.export_val_growth_pct_5*100), \
                                        past_export_val=num_format(past_yo.export_val), past_year=past_yr, current_export_val=num_format(this_yo.export_val), current_year=self.year)
            top_exports = yop_base.order_by(desc("export_val")).limit(2).all()
            if top_exports:
                export_subtitle += _(u"The most recent exports are led by %(top_export)s, which represent %(top_export_pct)s%% of the total exports of %(country)s, followed by %(second_export)s, which account for %(second_export_pct)s%%.",
                                        top_export=top_exports[0].product.get_profile_link(), top_export_pct=num_format((top_exports[0].export_val/exp_val_stat["val"])*100), \
                                        country=self.attr.get_name(article=True), second_export=top_exports[1].product.get_profile_link(), second_export_pct=num_format((top_exports[1].export_val/exp_val_stat["val"])*100))
        imp_val_stat = filter(lambda s: s["key"] == "import_val", self.stats())
        if imp_val_stat:
            imp_val_stat = imp_val_stat.pop()
            imp_rank = num_format(imp_val_stat["rank"], "ordinal") if imp_val_stat["rank"] > 1 else ""
            import_subtitle = _(u"In %(year)s %(country)s imported $%(import_val)s, making it the %(import_rank)s largest importer in the world. ",
                                year=self.year, country=self.attr.get_name(article=True), import_val=num_format(imp_val_stat["val"]), import_rank=imp_rank)
            if past_yo:
                chg = "increased" if this_yo.import_val_growth_pct_5 >= 0 else "decreased"
                import_subtitle += _(u"During the last five years the imports of %(country)s have %(increased_decreased)s at an annualized rate of %(change_rate)s%%, from $%(past_import_val)s in %(past_year)s to $%(current_import_val)s in %(current_year)s. ",
                                        country=self.attr.get_name(article=True), increased_decreased=chg, change_rate=num_format(this_yo.import_val_growth_pct_5*100), \
                                        past_import_val=num_format(past_yo.import_val), past_year=past_yr, current_import_val=num_format(this_yo.import_val), current_year=self.year)
            top_imports = yop_base.order_by(desc("import_val")).limit(2).all()
            if top_imports:
                import_subtitle += _(u"The most recent imports are led by %(top_import)s, which represent %(top_import_pct)s%% of the total imports of %(country)s, followed by %(second_import)s, which account for %(second_import_pct)s%%.",
                                        top_import=top_imports[0].product.get_profile_link(), top_import_pct=num_format((top_imports[0].import_val/imp_val_stat["val"])*100), \
                                        country=self.attr.get_name(article=True), second_import=top_imports[1].product.get_profile_link(), second_import_pct=num_format((top_imports[1].import_val/imp_val_stat["val"])*100))

        dests_tmap = Build("tree_map", "hs92", "export", self.attr, "show", "all", self.year)
        yod_exp = self.models.Yod.query.filter_by(year = self.year, origin = self.attr).order_by(desc("export_val")).limit(5).all()
        if yod_exp:
            dest_list = self.stringify_items(yod_exp, "export_val", "dest")
            dest_subtitle = _(u"The top export destinations of %(country)s are %(destinations)s.", country=self.attr.get_name(article=True), destinations=dest_list)

        origins_tmap = Build("tree_map", "hs92", "import", self.attr, "show", "all", self.year)
        yod_imp = self.models.Yod.query.filter_by(year = self.year, dest = self.attr).order_by(desc("export_val")).limit(5).all()
        if yod_imp:
            origin_list = self.stringify_items(yod_imp, "export_val", "origin")
            origin_subtitle = _(u"The top import origins of %(country)s are %(origins)s.", country=self.attr.get_name(article=True), origins=origin_list)

        # trade balance viz --
        first_yo = self.models.Yo.query.filter_by(year = available_years["hs92"][-1], country = self.attr).first()
        tb_subtitle = ""
        tb_build = Build("line", "hs92", "show", self.attr, "all", "all", available_years["hs92"])
        if first_yo:
            net_trade = this_yo.export_val - this_yo.import_val
            trade_balance = _("positive") if net_trade >= 0 else _("negative")
            trade_direction = _("exports") if net_trade >= 0 else _("imports")
            tb_subtitle = _(u"As of %(year)s %(country)s had a %(positive_negative)s trade balance of $%(net_trade)s in net %(exports_imports)s.",
                            year=self.year, country=self.attr.get_name(article=True), positive_negative=trade_balance, net_trade=num_format(abs(net_trade)), exports_imports=trade_direction)
            old_yo = self.models.Yo.query.filter_by(year = available_years["hs92"][0], country = self.attr).first()
            if old_yo:
                old_net_trade = old_yo.export_val - old_yo.import_val
                old_trade_balance = _("positive") if old_net_trade >= 0 else _("negative")
                old_trade_direction = _("exports") if old_net_trade >= 0 else _("imports")
                is_diff = True if old_trade_balance != trade_balance else False
                still_or_not = _("still") if old_trade_balance == trade_balance else ""
                tb_subtitle += _(u" As compared to their trade balance in %(year)s when they %(still)s had a %(positive_negative)s trade balance of $%(net_trade)s in net %(exports_imports)s.",
                                year=available_years["hs92"][0], still=still_or_not, positive_negative=old_trade_balance, net_trade=num_format(abs(old_net_trade)), exports_imports=old_trade_direction)

        trade_section = {
            "builds": [
                {"title": _(u"Exports"), "build": export_tmap, "subtitle": export_subtitle, "tour":"This is just a test", "seq":5},
                {"title": _(u"Imports"), "build": import_tmap, "subtitle": import_subtitle},
                {"title": _(u"Trade Balance"), "build": tb_build, "subtitle": tb_subtitle},
                {"title": _(u"Destinations"), "build": dests_tmap, "subtitle": dest_subtitle},
                {"title": _(u"Origins"), "build": origins_tmap, "subtitle": origin_subtitle},
            ]
        }
        sections.append(trade_section)

        ''' Product Space Section
        '''
        num_exports_w_rca = db.session.query(func.count(self.models.Yop.hs92_id)) \
                    .filter_by(year = self.year, origin = self.attr) \
                    .filter(self.models.Yop.export_rca >= 1) \
                    .filter(func.char_length(self.models.Yop.hs92_id)==6) \
                    .scalar()
        this_attr_yo = attrs.Yo.query.filter_by(year = self.year, country = self.attr).first()
        if this_attr_yo:
            eci = this_attr_yo.eci
            eci_rank = this_attr_yo.eci_rank
            if eci_rank:
                subtitle = _(u"The economy of %(country)s has an Economic Complexity Index (ECI) of %(eci)s making it the %(eci_rank)s most complex country. ",
                            country=self.attr.get_name(article=True), eci=num_format(eci), eci_rank=num_format(eci_rank, "ordinal"))
            else:
                subtitle = ""
            subtitle += _(u"%(country)s exports %(num_of_exports)s products with revealed comparative advantage " \
                u"(meaning that its share of global exports is larger than what " \
                u"would be expected from the size of its export economy " \
                u"and from the size of a product’s global market).",
                country=self.attr.get_name(article=True), num_of_exports=num_exports_w_rca)
        else:
            subtitle = ""
        product_space = Build("network", "hs92", "export", self.attr, "all", "show", self.year)
        ps_section = {
            "title": _(u"Economic Complexity of %(country)s", country=self.attr.get_name()),
            "subtitle": subtitle,
            "builds": [
                {"title": _(u"Product Space"), "build": product_space, "subtitle": _(u"The product space is a network connecting products that are likely to be co-exported and can be used to predict the evolution of a country’s export structure."), "tour":"The product space...", "seq":6}
            ]
        }

        if this_attr_yo and this_attr_yo.eci != None:
            line_rankings = Build("line", "sitc", "eci", "show", self.attr, "all", [y for y in available_years["sitc"] if y >= 1964])
            ps_section["builds"].append({"title": _(u"ECI Ranking"), "build": line_rankings, "subtitle": _(u"Lorem Ipsum.")})

        sections.append(ps_section)

        ''' DataViva
        '''
        dv_country_id = "asrus" if self.attr.id == "eurus" else self.attr.id
        dv_munic_dest_iframe = "http://dataviva.info/apps/embed/tree_map/secex/all/all/{}/bra/?size=import_val&controls=false".format(dv_country_id)
        dv_munic_origin_iframe = "http://dataviva.info/apps/embed/tree_map/secex/all/all/{}/bra/?size=export_val&controls=false".format(dv_country_id)
        dv_munic_dest_subtitle = _(u"""
            This treemap shows the municipalities in Brazil that imported products from %(country)s.<br /><br />
            DataViva is a visualization tool that provides official data on trade, industries, and education throughout Brazil. If you would like more info or to create a similar site get in touch with us at <a href='mailto:oec@media.mit.edu'>oec@media.mit.edu</a>.<br />
            <a target='_blank' href='http://dataviva.info/apps/builder/tree_map/secex/all/all/%(dv_country_id)s/bra/?size=import_val&controls=false'><img src='http://en.dataviva.info/static/img/nav/DataViva.png' /></a>
            """, country=self.attr.get_name(article=True), dv_country_id=dv_country_id)
        dv_munic_origin_subtitle = _(u"""
            This treemap shows the municipalities in Brazil that exported products to %(country)s.<br /><br />
            DataViva is a visualization tool that provides official data on trade, industries, and education throughout Brazil. If you would like more info or to create a similar site get in touch with us at <a href='mailto:oec@media.mit.edu'>oec@media.mit.edu</a>.<br />
            <a target='_blank' href='http://dataviva.info/apps/builder/tree_map/secex/all/all/%(dv_country_id)s/bra/?size=export_val&controls=false'><img src='http://en.dataviva.info/static/img/nav/DataViva.png' /></a>
            """, country=self.attr.get_name(article=True), dv_country_id=dv_country_id)
        dv_section = {
            "title": u"More on {} from our sister sites".format(self.attr.get_name(article=True)),
            "source": "dataviva",
            "builds": [
                {"title": _(u"Brazilian Municipalities that import from %(country)s", country=self.attr.get_name(article=True)), "iframe": dv_munic_dest_iframe, "subtitle": dv_munic_dest_subtitle, "tour":"Profile pages also contain visualizations from other websites created by member of the OEC team. The following are 2 embeded visualization from DataViva, a similar visualization platorm centered around Brazilian data.", "seq":7},
                {"title": _(u"Brazilian Municipalities that export to %(country)s", country=self.attr.get_name(article=True)), "iframe": dv_munic_origin_iframe, "subtitle": dv_munic_origin_subtitle},
            ]
        }
        sections.append(dv_section)

        ''' Pantheon
        '''
        if self.attr.id_2char:
            pantheon_iframe = "http://pantheon.media.mit.edu:5000/treemap/country_exports/{}/all/-4000/2010/H15/pantheon/embed".format(self.attr.id_2char.upper())
            pantheon_link = "<a target='_blank' href='http://pantheon.media.mit.edu:5000/treemap/country_exports/{}/all/-4000/2010/H15/pantheon/'><img src='http://pantheon.media.mit.edu/pantheon_logo.png' /></a>".format(self.attr.id_2char.upper())
            pantheon_section = {
                "title": "Pantheon",
                "source": "pantheon",
                "builds": [
                    {"title": u"Cultural Production of {}".format(self.attr.get_name(article=True)),
                    "iframe": pantheon_iframe,
                    "subtitle": _(u"This treemap shows the cultural exports of %(country)s, as proxied by the production of globally famous historical characters.<br />%(pantheon_link)s", country=self.attr.get_name(), pantheon_link=pantheon_link),
                    "tour":"Pantheon...", "seq":8
                    },
                ]
            }
            sections.append(pantheon_section)

        return sections

class Product(Profile):

    def __init__(self, classification, id):
        super(Product, self).__init__(classification, id)
        self.classification = classification
        self.attr_cls = getattr(attrs, classification.capitalize())
        self.attr = self.attr_cls.query.filter(getattr(self.attr_cls, classification) == self.id).first()
        self.depth = len(self.attr.id) if self.attr else None
        self.cached_stats = []

    def stats(self):
        if not self.cached_stats:
            all_stats = [("export_val", _('Exports')), ("pci", _('Product Complexity')), ("top_exporter", _('Top Exporter')), ("top_importer", _('Top Importer'))]
            yp_historic = self.models.Yp.query.filter_by(product=self.attr).all()
            yp_base_q = self.models.Yp.query.filter_by(year=self.year).filter(getattr(self.models.Yp, "{}_id_len".format(self.classification)) == self.depth)
            this_yp = yp_base_q.filter_by(product=self.attr).first()
            if this_yp:
                for stat_type, stat_title in all_stats:
                    this_stat = {}
                    if "top" not in stat_type:
                        res = yp_base_q.order_by(desc(stat_type)).all()
                        this_stat = {"rank": res.index(this_yp)+1, "total": len(res), \
                                        "sparkline": {
                                            "val": [float(getattr(yh, stat_type)) if getattr(yh, stat_type) is not None else 0 for yh in yp_historic], \
                                            "start":available_years[self.classification][0], "end":available_years[self.classification][-1]}
                                    }
                    this_stat["val"] = getattr(this_yp, stat_type)
                    this_stat["title"] = stat_title
                    this_stat["key"] = stat_type
                    self.cached_stats.append(this_stat)
        return self.cached_stats

    def hierarchy(self):
        prods = []

        _2dig = self.attr_cls.query.get(self.attr.id[:2])
        prods.append(_2dig)

        '''if this is a 2 digit product show only its children,
            on the other hand if its a 4 or 6 digit product show
            the single 4 digit prod and all 6 digit children with
            itself included'''
        if self.attr == _2dig:
            children = self.attr_cls.query \
                        .filter(self.attr_cls.id.startswith(_2dig.id)) \
                        .filter(func.char_length(self.attr_cls.id) == 6) \
                        .order_by("id") \
                        .all()
            prods = prods + list(children)
        else:
            _4dig = self.attr_cls.query.get(self.attr.id[:6])
            prods.append(_4dig)
            children = self.attr_cls.query \
                        .filter(self.attr_cls.id.startswith(_4dig.id)) \
                        .filter(func.char_length(self.attr_cls.id) == 8) \
                        .order_by("id") \
                        .all()
            prods = prods + list(children)

        return prods


    def intro(self):
        all_paragraphs = []

        ''' Paragraph #2
        '''
        # get total world trade rank
        this_yp = self.models.Yp.query.filter_by(year = self.year, product = self.attr).first()
        all_yp = self.models.Yp.query.filter_by(year = self.year) \
                    .filter(func.char_length(getattr(self.models.Yp, "{}_id".format(self.classification))) == len(self.attr.id)) \
                    .order_by(desc("export_val")).all()
        if this_yp:
            econ_rank = num_format(all_yp.index(this_yp) + 1, "ordinal") if all_yp.index(this_yp) else ""
            # get PCI ranking
            p2 = _(u"%(product)s the %(economic_rank)s most traded product", product=self.attr.get_name(verb=True), economic_rank=econ_rank)
            pci_rank = this_yp.pci_rank
            if pci_rank:
                pci_rank = num_format(pci_rank, "ordinal") if pci_rank > 1 else ""
                p2 += _(u" and the %(pci_rank)s most complex product according to the <a href='/en/rankings/hs92/'>Product Complexity Index (PCI)</a>", pci_rank=pci_rank)
            p2 += "."
            all_paragraphs.append(p2)

        ''' Paragraph #3
        '''
        yop_exp = self.models.Yop.query.filter_by(year = self.year, product = self.attr).filter(self.models.Yop.export_val!=None).order_by(desc("export_val")).limit(5).all()
        if yop_exp:
            exporters = self.stringify_items(yop_exp, "export_val", "origin")
            yop_imp = self.models.Yop.query.filter_by(year=self.year, product=self.attr).filter(self.models.Yop.import_val!=None).order_by(desc("import_val")).limit(5).all()
            importers = self.stringify_items(yop_imp, "import_val", "origin")
            p3 = _(u"The top exporters of %(product)s are %(exporters)s. The top importers are %(importers)s.",
                    product=self.attr.get_name(), exporters=exporters, importers=importers)
            all_paragraphs.append(p3)

        ''' Paragraph #4
        '''
        p4 = []
        # find out which countries this product is their #1 export/import
        countries_top = self.models.Yo.query.filter_by(year = self.year)
        if len(self.attr.id) == 6:
            countries_top_export = countries_top.filter_by(top_export_hs4 = self.attr.id)
            countries_top_import = countries_top.filter_by(top_import_hs4 = self.attr.id)
        elif len(self.attr.id) == 8:
            countries_top_export = countries_top.filter_by(top_export_hs6 = self.attr.id)
            countries_top_import = countries_top.filter_by(top_import_hs6 = self.attr.id)
        countries_top_export = countries_top_export.all()
        countries_top_import = countries_top_import.all()
        if countries_top_export:
            countries_top_export = self.stringify_items(countries_top_export, None, "country")
            p4.append(_(u"%(product)s the top export of %(countries)s.", product=self.attr.get_name(verb=True), countries=countries_top_export))
        if countries_top_import:
            countries_top_import = self.stringify_items(countries_top_import, None, "country")
            p4.append(_(u"%(product)s the top import of %(countries)s.", product=self.attr.get_name(verb=True), countries=countries_top_import))
        if p4:
            all_paragraphs = all_paragraphs + p4

        ''' Paragraph #5
        '''
        keywords = self.attr.get_keywords()
        if keywords:
            all_paragraphs.append(_(u"%(product)s also known as %(keywords)s.", product=self.attr.get_name(verb=True), keywords=keywords))

        ''' Paragraph #1
        '''
        p1 = _(u"%(product)s a %(product_id_length)s digit %(classification)s product.", product=self.attr.get_name(verb=True), product_id_length=len(self.attr.get_display_id()), classification=self.classification.upper())
        all_paragraphs.append(p1)

        return all_paragraphs


    def sections(self):
        sections = []
        ''' Trade Section
        '''
        trade_section = {
            "title": u"{} Trade".format(self.attr.get_name()),
            "builds": []
        }

        exporters = Build("tree_map", self.classification, "export", "show", "all", self.attr, self.year)
        exporters_subtitle = u"This treemap shows the share of countries that export {}.".format(self.attr.get_name())
        trade_section["builds"].append({"title": u"Exporters", "build": exporters, "subtitle": exporters_subtitle})

        importers = Build("tree_map", self.classification, "import", "show", "all", self.attr, self.year)
        importers_subtitle = u"This treemap shows the share of countries that import {}.".format(self.attr.get_name())
        trade_section["builds"].append({"title": u"Importers", "build": importers, "subtitle": importers_subtitle})

        rings = Build("rings", self.classification, "export", "all", "all", self.attr, self.year)
        rings_subtitle = u"This visualization shows products that are likely to be exported by countries that export {}.".format(self.attr.get_name())
        trade_section["builds"].append({"title": u"Product Connections", "build": rings, "subtitle": rings_subtitle})

        sections.append(trade_section)

        ''' DataViva Section
        '''
        if self.classification == "hs92":
            dv_hs = self.attr
            if len(dv_hs.id) > 6:
                dv_hs = self.attr_cls.query.get(self.attr.id[:6])
            dv_munic_exporters_iframe = "http://en.dataviva.info/apps/embed/tree_map/secex/all/{}/all/bra/?controls=false&size=export_val".format(dv_hs.id)
            dv_munic_importers_iframe = "http://en.dataviva.info/apps/embed/tree_map/secex/all/{}/all/bra/?controls=false&size=import_val".format(dv_hs.id)
            dv_munic_exporters_subtitle = u"""
                This treemap shows the municipalities in Brazil that export {}.<br /><br />
                DataViva is a visualization tool that provides official data on trade, industries, and education throughout Brazil. If you would like more info or to create a similar site get in touch with us at <a href='mailto:oec@media.mit.edu'>oec@media.mit.edu</a>.<br />
                <a target='_blank' href='http://en.dataviva.info/apps/builder/tree_map/secex/all/{}/all/bra/?controls=false&size=export_val'><img src='http://en.dataviva.info/static/img/nav/DataViva.png' /></a>
                """.format(dv_hs.get_name(), self.attr.id)
            dv_munic_importers_subtitle = u"""
                This treemap shows the municipalities in Brazil that import {}.<br />.<br />
                DataViva is a visualization tool that provides official data on trade, industries, and education throughout Brazil. If you would like more info or to create a similar site get in touch with us at <a href='mailto:oec@media.mit.edu'>oec@media.mit.edu</a>.<br />
                <a target='_blank' href='http://en.dataviva.info/apps/builder/tree_map/secex/all/{}/all/bra/?controls=false&size=import_val'><img src='http://en.dataviva.info/static/img/nav/DataViva.png' /></a>
                """.format(dv_hs.get_name(), self.attr.id)
            dv_section = {
                "title": u"More on {} from our sister sites".format(self.attr.get_name()),
                "source": "dataviva",
                "builds": [
                    {"title": u"{} exporters in Brazil".format(dv_hs.get_name()), "iframe": dv_munic_exporters_iframe, "subtitle": dv_munic_exporters_subtitle},
                    {"title": u"{} importers in Brazil".format(dv_hs.get_name()), "iframe": dv_munic_importers_iframe, "subtitle": dv_munic_importers_subtitle},
                ]
            }
            sections.append(dv_section)

        return sections
