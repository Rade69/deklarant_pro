import logging
logger = logging.getLogger(__name__)
"""XML importer za ASYCUDA deklaracije."""

from pathlib import Path
from typing import Any, Dict, List
import xml.etree.ElementTree as ET

from core.draft import InvoiceLine


class XMLImporter:
    """Uvozi ASYCUDA XML deklaracije."""

    def __init__(self):
        """Inicijalizuje XML importer."""
        pass

    def import_file(self, file_path: Path, format_type: str = "auto") -> Dict[str, Any]:
        """
        Uvozi ASYCUDA XML fajl.

        Args:
            file_path: Putanja do XML fajla
            format_type: Tip formata - "world", "pro", ili "auto" (default: "auto")

        Returns:
            Dictionary sa podacima deklaracije

        Raises:
            FileNotFoundError: Ako fajl ne postoji
            ValueError: Ako XML format nije validan
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Fajl ne postoji: {file_path}")

        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # Auto detekcija formata
            if format_type.lower() == "auto":
                format_type = self._detect_xml_format(root)
            
            if format_type.lower() == "pro":
                return self._parse_asycuda_pro_xml(root)
            else:
                return self._parse_asycuda_xml(root)
        except ET.ParseError as e:
            raise ValueError(f"Neispravan XML format: {e}")
    
    def _detect_xml_format(self, root: ET.Element) -> str:
        """
        Automatski detektuje tip XML formata.
        
        Args:
            root: Root XML element
        
        Returns:
            "world" ili "pro"
        """
        root_tag = root.tag.upper().replace('{', '').replace('}', '')
        
        # Pro format često sadrži "DECLARATION" u tagu
        if 'DECLARATION' in root_tag:
            return "pro"
        
        # World format često ima "ASYCUDA" kao root
        if 'ASYCUDA' in root_tag:
            return "world"
        
        # Proveri namespace
        if root.tag.startswith('{'):
            uri = root.tag.split('}')[0][1:]
            if 'asycuda' in uri.lower() and 'pro' in uri.lower():
                return "pro"
        
        # Podrazumevano: World format
        logger.warning(f"Nije moguće detektovati format XML-a (root tag: {root_tag}), podrazumevam World format")
        return "world"

    def _parse_asycuda_xml(self, root: ET.Element) -> Dict[str, Any]:
        """
        Parsira ASYCUDA XML strukturu.

        Args:
            root: Root XML element

        Returns:
            Dictionary sa parsiranim podacima (sa 'items' i 'header' ključem)
        """
        items = self._parse_items(root)
        header = self._parse_header(root)

        logger.debug(f"DEBUG: XML parsed - items count: {len(items)}, header keys: {list(header.keys())}")
        if header:
            logger.debug(f"DEBUG: Header data: {header}")
        return {
            'items': items,
            'header': header,
            'item_count': len(items)
        }

    def _parse_header(self, element: ET.Element) -> Dict[str, Any]:
        """Parsira zaglavlje deklaracije."""
        header_data = {}
        
        # Pokušaj da pronađeš element zaglavlja na više načina
        header_elements = ['AsycudaDocument', 'Document', 'Declaration', 'Header']
        
        for header_tag in header_elements:
            header_elem = element.find(header_tag)
            if header_elem is not None:
                # Ako se koristi namespace, pokušaj i sa namespace-om
                namespace = {}
                if element.tag.startswith('{'):
                    uri = element.tag.split('}')[0][1:]
                    namespace['ns'] = uri
                
                def find_with_namespace(parent, tag):
                    # Pokušaj sa namespace-om
                    if namespace:
                        result = parent.find('ns:' + tag, namespace)
                        if result is not None:
                            return result
                    # Pokušaj bez namespace-a
                    result = parent.find(tag)
                    return result
                
                # Parsiranje podataka iz zaglavlja
                # Izvoznik (Exporter)
                exporter_elem = find_with_namespace(header_elem, 'Exporter')
                if exporter_elem is not None:
                    header_data['izvoznik_id'] = self._get_text(exporter_elem, ['RegistrationNumber', 'ID', 'Code'], default="")
                    header_data['izvoznik_naziv'] = self._get_text(exporter_elem, ['Name', 'CompanyName'], default="")
                    header_data['izvoznik_adresa'] = self._get_text(exporter_elem, ['Address', 'Street'], default="")
                    header_data['izvoznik_grad'] = self._get_text(exporter_elem, ['City'], default="")
                    header_data['izvoznik_postanski_broj'] = self._get_text(exporter_elem, ['PostalCode'], default="")
                    header_data['izvoznik_drzava'] = self._get_text(exporter_elem, ['Country'], default="")
                
                # Primalac (Consignee)
                consignee_elem = find_with_namespace(header_elem, 'Consignee')
                if consignee_elem is not None:
                    header_data['primalac_id'] = self._get_text(consignee_elem, ['RegistrationNumber', 'ID', 'Code'], default="")
                    header_data['primalac_naziv'] = self._get_text(consignee_elem, ['Name', 'CompanyName'], default="")
                    header_data['primalac_adresa'] = self._get_text(consignee_elem, ['Address', 'Street'], default="")
                    header_data['primalac_grad'] = self._get_text(consignee_elem, ['City'], default="")
                    header_data['primalac_postanski_broj'] = self._get_text(consignee_elem, ['PostalCode'], default="")
                    header_data['primalac_drzava'] = self._get_text(consignee_elem, ['Country'], default="")
                
                # Deklarant (Declarant)
                declarant_elem = find_with_namespace(header_elem, 'Declarant')
                if declarant_elem is not None:
                    header_data['deklarant_id'] = self._get_text(declarant_elem, ['RegistrationNumber', 'ID', 'Code'], default="")
                    header_data['deklarant_naziv'] = self._get_text(declarant_elem, ['Name', 'CompanyName'], default="")
                    header_data['deklarant_adresa'] = self._get_text(declarant_elem, ['Address', 'Street'], default="")
                    header_data['deklarant_grad'] = self._get_text(declarant_elem, ['City'], default="")
                    header_data['deklarant_postanski_broj'] = self._get_text(declarant_elem, ['PostalCode'], default="")
                    header_data['deklarant_drzava'] = self._get_text(declarant_elem, ['Country'], default="")
                
                # Deklaracija (Declaration)
                declaration_elem = find_with_namespace(header_elem, 'Declaration')
                if declaration_elem is not None:
                    header_data['deklaracija_tip'] = self._get_text(declaration_elem, ['Type', 'DocumentType'], default="")
                    header_data['deklaracija_a'] = self._get_text(declaration_elem, ['A', 'FormA'], default="")
                    header_data['deklaracija_oznaka'] = self._get_text(declaration_elem, ['H', 'FormH'], default="")
                
                # Obrasci i tovarni listovi
                header_data['obrazac_1'] = self._get_text(header_elem, ['Form1', 'FormA'], default="")
                header_data['obrazac_2'] = self._get_text(header_elem, ['Form2', 'FormB'], default="")
                header_data['tovarni_listovi'] = self._get_text(header_elem, ['BillOfLading', 'TransportDoc'], default="")
                
                # Stavke, paketi, referentni broj
                header_data['stavke'] = self._get_text(header_elem, ['Items', 'ItemCount'], default="")
                header_data['uk_paketa'] = self._get_text(header_elem, ['Packages', 'PackageCount'], default="")
                header_data['ref_br'] = self._get_text(header_elem, ['ReferenceNumber', 'RefNo'], default="")
                
                # Odgovorna zemlja
                header_data['odg_zemlja_1'] = self._get_text(header_elem, ['ResponsibleCountryCode'], default="")
                header_data['odg_zemlja_2'] = self._get_text(header_elem, ['ResponsibleCountryName'], default="")
                header_data['odg_zemlja_3'] = self._get_text(header_elem, ['AdditionalInfo1'], default="")
                header_data['odg_zemlja_4'] = self._get_text(header_elem, ['AdditionalInfo2'], default="")
                
                # Zemlje (10, 11, 12, 13)
                header_data['zem_10'] = self._get_text(header_elem, ['DispatchCountry', 'CountryOfDispatch'], default="")
                header_data['zem_11'] = self._get_text(header_elem, ['TradeCountry', 'TradingCountry'], default="")
                header_data['zem_12'] = self._get_text(header_elem, ['Value', 'TotalValue'], default="")
                header_data['zem_13'] = self._get_text(header_elem, ['CAP', 'CustomsAuthorization'], default="")
                
                # Države izvoza, porijekla i odredišta
                header_data['drzava_izvoza_naziv'] = self._get_text(header_elem, ['ExportCountryName'], default="")
                header_data['drzava_izvoza_sifra'] = self._get_text(header_elem, ['ExportCountryCode'], default="")
                header_data['drzava_porijekla'] = self._get_text(header_elem, ['OriginCountry', 'CountryOfOrigin'], default="")
                header_data['drzava_odredista_naziv'] = self._get_text(header_elem, ['DestinationCountryName'], default="")
                header_data['drzava_odredista_sifra'] = self._get_text(header_elem, ['DestinationCountryCode'], default="")
                
                # Uslovi isporuke
                header_data['uslovi_kod'] = self._get_text(header_elem, ['DeliveryTermsCode'], default="")
                header_data['uslovi_mjesto'] = self._get_text(header_elem, ['DeliveryPlace'], default="")
                
                # Carinske kancelarije i lokacije
                header_data['izlazna_carinarnica'] = self._get_text(header_elem, ['ExitCustomsOffice'], default="")
                header_data['lokacija_robe'] = self._get_text(header_elem, ['GoodsLocation'], default="")
                
                # Aktivno transportno sredstvo na granici
                header_data['aktivno_transport'] = self._get_text(header_elem, ['ActiveBorderTransport'], default="")
                
                break  # Samo prvi pronađeni element zaglavlja
        
        return header_data

    def _parse_items(self, root: ET.Element) -> List[InvoiceLine]:
        """
        Parsira stavke robe iz ASYCUDA XML-a.

        Args:
            root: Root XML element

        Returns:
            Lista InvoiceLine objekata
        """
        items = []

        # Find all Declaration_item elements (može biti različita struktura)
        # Try multiple possible paths
        item_elements = (
            root.findall('.//Declaration_item') or
            root.findall('.//Item') or
            root.findall('.//GoodsShipment/GovernmentAgencyGoodsItem')
        )

        for idx, item_elem in enumerate(item_elements, start=1):
            try:
                # Extract data from XML
                item_number = self._get_text(item_elem, [
                    'Item_Number', 'SequenceNumeric', 'LineID'
                ], default=str(idx))

                # Goods description - rubrika 31, Commercial_Description ima prednost
                goods_desc = self._get_text(item_elem, [
                    'Goods_description/Commercial_Description',
                    'Goods_description/Description_of_goods',
                    'Goods_description',
                    'Description',
                    'Commodity/Description'
                ], default="")

                # Tariff code - ASYCUDA putanja
                tariff_code = self._get_text(item_elem, [
                    'Tarification/HScode/Commodity_code',
                    'Commodity_code',
                    'Tariff_code',
                    'Commodity/Classification/ID'
                ], default="")

                # Country of origin - unutar Goods_description u ASYCUDA XML-u
                country_code = self._get_text(item_elem, [
                    'Goods_description/Country_of_origin_code',
                    'Country_of_origin_code',
                    'Origin_country_code',
                    'Origin/CountryCode'
                ], default="")

                # Povlastica (rubrika 36) - unutar Tarification u ASYCUDA XML-u
                povlastica = self._get_text(item_elem, [
                    'Tarification/Preference_code',
                    'Preference_code',
                ], default="")

                # Gross weight - ASYCUDA putanja
                gross_weight = self._get_float(item_elem, [
                    'Valuation_item/Weight_itm/Gross_weight_itm',
                    'Gross_weight',
                    'GrossMassMeasure',
                    'PackagingMarks/GrossMassMeasure'
                ])

                # Net weight - ASYCUDA putanja
                net_weight = self._get_float(item_elem, [
                    'Valuation_item/Weight_itm/Net_weight_itm',
                    'Net_weight',
                    'NetNetWeightMeasure'
                ])

                # Količina
                quantity = self._get_float(item_elem, [
                    'Supplementary_unit/Suppplementary_unit_quantity',
                    'Supplementary_quantity',
                    'TariffQuantity',
                    'Commodity/GoodsMeasure/TariffQuantity'
                ], default=1.0)

                # Amount - ASYCUDA putanja
                amount = self._get_float(item_elem, [
                    'Valuation_item/Item_Invoice/Amount_foreign_currency',
                    'Valuation_item/Statistical_value',
                    'Item_price/Amount_national_currency',
                    'CustomsValuation/ChargeAmount',
                    'Amount'
                ])

                # Currency - ASYCUDA putanja
                currency = self._get_text(item_elem, [
                    'Valuation_item/Item_Invoice/Currency_code',
                    'Item_price/Currency_code',
                    'CustomsValuation/ChargeAmount[@currencyID]',
                    'CurrencyCode'
                ], default="EUR")

                # Create InvoiceLine
                invoice_line = InvoiceLine(
                    line_no=int(item_number) if item_number.isdigit() else idx,
                    naziv_robe=goods_desc,
                    tarifni_broj=tariff_code,
                    zemlja_porijekla=country_code,
                    povlastica=povlastica,
                    bruto_kg=gross_weight,
                    neto_kg=net_weight,
                    kolicina=quantity,
                    cijena_jed=amount / quantity if quantity > 0 and amount > 0 else amount,
                    iznos=amount,
                    valuta=currency,
                    jm="KOM"  # Default
                )

                items.append(invoice_line)

            except Exception as e:
                logger.debug(f"Warning: Greška pri parsiranju stavke {idx}: {e}")
                continue

        return items

    def _get_text(self, element: ET.Element, paths: List[str], default: str = "") -> str:
        """
        Pokušaj da pronađeš tekst iz više mogućih XML putanja.

        Args:
            element: XML element
            paths: Lista mogućih XPath putanja
            default: Default vrijednost ako ništa nije pronađeno

        Returns:
            Tekst iz prvog pronađenog elementa ili default
        """
        for path in paths:
            found = element.find(path)
            if found is not None and found.text:
                return found.text.strip()

        return default

    def _get_float(self, element: ET.Element, paths: List[str], default: float = 0.0) -> float:
        """
        Pokušaj da pronađeš float vrijednost iz više mogućih XML putanja.

        Args:
            element: XML element
            paths: Lista mogućih XPath putanja
            default: Default vrijednost ako ništa nije pronađeno

        Returns:
            Float vrijednost ili default
        """
        text = self._get_text(element, paths, default="")

        if text:
            try:
                return float(text.replace(',', '.'))
            except (ValueError, TypeError):
                pass

        return default

    def _parse_asycuda_pro_xml(self, root: ET.Element) -> Dict[str, Any]:
        """
        Parsira ASYCUDA Pro XML strukturu.
        
        ASYCUDA Pro koristi drugačiju strukturu od World formata.
        Osnovni root je <Declaration> sa namespace-om.
        
        Args:
            root: Root XML element

        Returns:
            Dictionary sa parsiranim podacima
        """
        # Proveri da li je Pro format
        # U Pro formatu, root može biti <Declaration> ili <DECLARATION>
        root_tag = root.tag.upper().replace('{', '').replace('}', '')
        if 'DECLARATION' not in root_tag:
            # Ako nije Pro format, probaj World parser
            logger.warning("XML ne izgleda kao ASYCUDA Pro format, pokušavam World parser")
            return self._parse_asycuda_xml(root)
        
        items = self._parse_pro_items(root)
        header = self._parse_pro_header(root)
        
        logger.debug(f"DEBUG: ASYCUDA Pro XML parsed - items count: {len(items)}, header keys: {list(header.keys())}")
        return {
            'items': items,
            'header': header,
            'item_count': len(items),
            'format': 'pro'
        }
    
    def _parse_pro_header(self, root: ET.Element) -> Dict[str, Any]:
        """Parsira zaglavlje ASYCUDA Pro XML-a."""
        header_data = {}
        
        # Namespace handling
        ns = {}
        if root.tag.startswith('{'):
            uri = root.tag.split('}')[0][1:]
            ns['ns'] = uri
        
        def find_with_ns(parent, tag):
            if ns:
                result = parent.find(f"ns:{tag}", ns)
                if result is not None:
                    return result
            return parent.find(tag)
        
        # Osnovni podaci deklaracije
        # Broj deklaracije
        decl_number = find_with_ns(root, 'DeclarationNumber')
        if decl_number is not None and decl_number.text:
            header_data['broj_deklaracije'] = decl_number.text.strip()
        
        # Datum
        decl_date = find_with_ns(root, 'DeclarationDate')
        if decl_date is not None and decl_date.text:
            header_data['datum'] = decl_date.text.strip()
        
        # Tip deklaracije
        decl_type = find_with_ns(root, 'DeclarationType')
        if decl_type is not None and decl_type.text:
            header_data['vrsta_deklaracije'] = decl_type.text.strip()
        
        # Izvoznik
        exporter = find_with_ns(root, 'Exporter')
        if exporter is not None:
            header_data['izvoznik_id'] = self._get_text(exporter, ['ID', 'Code', 'Number'], default="")
            header_data['izvoznik_naziv'] = self._get_text(exporter, ['Name', 'CompanyName'], default="")
            header_data['izvoznik_adresa'] = self._get_text(exporter, ['Address', 'Street'], default="")
            header_data['izvoznik_grad'] = self._get_text(exporter, ['City', 'Town'], default="")
            header_data['izvoznik_postanski_broj'] = self._get_text(exporter, ['PostalCode', 'ZipCode'], default="")
            header_data['izvoznik_drzava'] = self._get_text(exporter, ['Country', 'CountryCode'], default="")
        
        # Primalac
        consignee = find_with_ns(root, 'Consignee')
        if consignee is not None:
            header_data['primalac_id'] = self._get_text(consignee, ['ID', 'Code', 'Number'], default="")
            header_data['primalac_naziv'] = self._get_text(consignee, ['Name', 'CompanyName'], default="")
            header_data['primalac_adresa'] = self._get_text(consignee, ['Address', 'Street'], default="")
            header_data['primalac_grad'] = self._get_text(consignee, ['City', 'Town'], default="")
            header_data['primalac_postanski_broj'] = self._get_text(consignee, ['PostalCode', 'ZipCode'], default="")
            header_data['primalac_drzava'] = self._get_text(consignee, ['Country', 'CountryCode'], default="")
        
        # Transport
        transport = find_with_ns(root, 'TransportMeans')
        if transport is not None:
            header_data['transport_id'] = self._get_text(transport, ['ID', 'Number'], default="")
            header_data['aktivno_transport'] = self._get_text(transport, ['Nationality', 'Country'], default="")
        
        # Carinska ispostava
        customs_office = find_with_ns(root, 'CustomsOffice')
        if customs_office is not None:
            header_data['izlazna_carinarnica'] = self._get_text(customs_office, ['Code', 'Number'], default="")
        
        return header_data
    
    def _parse_pro_items(self, root: ET.Element) -> List[InvoiceLine]:
        """Parsira stavke iz ASYCUDA Pro XML-a."""
        items = []
        
        # Namespace handling
        ns = {}
        if root.tag.startswith('{'):
            uri = root.tag.split('}')[0][1:]
            ns['ns'] = uri
        
        def find_with_ns(parent, tag):
            if ns:
                result = parent.find(f"ns:{tag}", ns)
                if result is not None:
                    return result
            return parent.find(tag)
        
        # Pronađi sve GoodsItem elemente
        goods_items = []
        # Pokušaj različite putanje
        goods_items = root.findall('.//GoodsItem') or root.findall('.//GOODSITEM') or root.findall('.//Item')
        
        for idx, item_elem in enumerate(goods_items, start=1):
            try:
                # Broj stavke
                item_number = self._get_text(item_elem, ['ItemNumber', 'SequenceNumber', 'Number'], default=str(idx))
                
                # Opis robe
                description = self._get_text(item_elem, [
                    'Description',
                    'GoodsDescription',
                    'CommercialDescription'
                ], default="")
                
                # Tarifni broj
                tariff_code = self._get_text(item_elem, [
                    'CommodityCode',
                    'HS Code',
                    'TariffCode'
                ], default="")
                
                # Zemlja porekla
                origin_country = self._get_text(item_elem, [
                    'OriginCountry',
                    'CountryOfOrigin',
                    'Origin'
                ], default="")
                
                # Količina
                quantity = self._get_float(item_elem, [
                    'Quantity',
                    'NetWeight',
                    'GrossWeight'
                ], default=1.0)
                
                # Vrednost
                value = self._get_float(item_elem, [
                    'Value',
                    'ItemValue',
                    'StatisticalValue'
                ], default=0.0)
                
                # Valuta
                currency = self._get_text(item_elem, [
                    'Currency',
                    'CurrencyCode'
                ], default="EUR")
                
                # Težina
                gross_weight = self._get_float(item_elem, [
                    'GrossWeight',
                    'GrossMass'
                ])
                
                net_weight = self._get_float(item_elem, [
                    'NetWeight',
                    'NetMass'
                ])
                
                # Kreiraj InvoiceLine
                invoice_line = InvoiceLine(
                    line_no=int(item_number) if item_number.isdigit() else idx,
                    naziv_robe=description,
                    tarifni_broj=tariff_code,
                    zemlja_porijekla=origin_country,
                    povlastica="",  # Pro format može imati drugačije polje
                    bruto_kg=gross_weight,
                    neto_kg=net_weight,
                    kolicina=quantity,
                    cijena_jed=value / quantity if quantity > 0 and value > 0 else value,
                    iznos=value,
                    valuta=currency,
                    jm="KOM"  # Default
                )
                
                items.append(invoice_line)
                
            except Exception as e:
                logger.debug(f"Warning: Greška pri parsiranju Pro stavke {idx}: {e}")
                continue
        
        return items

    def _parse_documents(self, element: ET.Element) -> list[Dict[str, Any]]:
        """Parsira dokumente."""
        # TODO: Implementirati
        return []
