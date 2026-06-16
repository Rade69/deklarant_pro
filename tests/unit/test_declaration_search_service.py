from pathlib import Path

from services.agent.chat import declaration_search_service as mod
from services.agent.chat.declaration_search_service import DeclarationSearchService


def test_default_declaration_index_points_to_project_data():
    assert mod.XML_DIR == mod.PROJECT_ROOT / "data" / "knowledge_base" / "NOVA ASIKUDA"
    assert mod.INDEX_DB == mod.PROJECT_ROOT / "data" / "knowledge_base" / "declaration_index.db"


def test_declaration_search_uses_env_paths(monkeypatch, tmp_path):
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    (xml_dir / "test.xml").write_text(
        """<ASYCUDA>
        <Traders>
          <Exporter><Exporter_name>TEST EXPORTER</Exporter_name></Exporter>
          <Consignee><Consignee_name>TEST CONSIGNEE</Consignee_name><Consignee_code>123</Consignee_code></Consignee>
        </Traders>
        <Item>
          <Tarification><HScode><Commodity_code>33049900</Commodity_code><Precision_1>000</Precision_1></HScode><Preference_code>EUPR</Preference_code></Tarification>
          <Goods_description>
            <Country_of_origin_code>FR</Country_of_origin_code>
            <Commercial_Description>DEPIWHITE ADV.KREM 40 ML</Commercial_Description>
            <Description_of_goods>Preparati za njegu koze</Description_of_goods>
          </Goods_description>
        </Item>
        <Item>
          <Tarification><HScode><Commodity_code>11010015</Commodity_code><Precision_1>000</Precision_1></HScode><Preference_code></Preference_code></Tarification>
          <Goods_description>
            <Country_of_origin_code>RS</Country_of_origin_code>
            <Commercial_Description>BRASNO T-500 EC 2286500</Commercial_Description>
            <Description_of_goods>Brasno od psenice</Description_of_goods>
          </Goods_description>
        </Item>
        </ASYCUDA>""",
        encoding="utf-8",
    )
    index_db = tmp_path / "idx" / "declaration_index.db"
    monkeypatch.setenv("XML_ARCHIVE_DIR", str(xml_dir))
    monkeypatch.setenv("DECLARATION_INDEX_DB", str(index_db))

    rows = DeclarationSearchService().search_by_goods("DEPIWHITE ADV.KREM 40 ml")

    assert len(rows) == 1
    assert rows[0]["country_origin"] == "FR"
    assert rows[0]["hs_code"] == "33049900000"
    assert Path(index_db).exists()


def test_declaration_search_requires_meaningful_token_overlap(monkeypatch, tmp_path):
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    (xml_dir / "test.xml").write_text(
        """<ASYCUDA>
        <Item>
          <Tarification><HScode><Commodity_code>21069098</Commodity_code><Precision_1>000</Precision_1></HScode><Preference_code>EUPR</Preference_code></Tarification>
          <Goods_description>
            <Country_of_origin_code>AT</Country_of_origin_code>
            <Commercial_Description>SUSSINA 650 TBL SUSSINA 200 TBL</Commercial_Description>
            <Description_of_goods>Prehrambeni proizvodi</Description_of_goods>
          </Goods_description>
        </Item>
        <Item>
          <Tarification><HScode><Commodity_code>11010015</Commodity_code><Precision_1>000</Precision_1></HScode><Preference_code></Preference_code></Tarification>
          <Goods_description>
            <Country_of_origin_code>RS</Country_of_origin_code>
            <Commercial_Description>BRASNO T-500 EC 2286500</Commercial_Description>
            <Description_of_goods>Brasno od psenice</Description_of_goods>
          </Goods_description>
        </Item>
        </ASYCUDA>""",
        encoding="utf-8",
    )
    index_db = tmp_path / "idx" / "declaration_index.db"
    monkeypatch.setenv("XML_ARCHIVE_DIR", str(xml_dir))
    monkeypatch.setenv("DECLARATION_INDEX_DB", str(index_db))

    rows = DeclarationSearchService().search_by_goods("SUSSINA 650 tbl", limit=5)

    assert len(rows) == 1
    assert rows[0]["country_origin"] == "AT"
    assert rows[0]["hs_code"] == "21069098000"
