"""Centralni mapper za mapiranje podataka."""

from typing import Any, Dict


class CentralMapper:
    """Mapira podatke iz različitih formata u Draft model."""

    def map_from_excel(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mapira Excel podatke u Draft format.

        Args:
            data: Sirovi Excel podaci

        Returns:
            Mapirani podaci spremni za Draft
        """
        # TODO: Implementirati mapiranje iz Excel formata
        return {}

    def map_from_pdf(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mapira PDF podatke u Draft format.

        Args:
            data: Sirovi PDF podaci

        Returns:
            Mapirani podaci spremni za Draft
        """
        # TODO: Implementirati mapiranje iz PDF formata
        return {}

    def map_from_xml(self, data: Dict[str, Any], format_type: str = "world") -> Dict[str, Any]:
        """
        Mapira XML podatke u Draft format.

        Args:
            data: Sirovi XML podaci
            format_type: Tip XML formata - "world" ili "pro"

        Returns:
            Mapirani podaci spremni za Draft
        """
        if format_type.lower() == "pro":
            return self._map_from_pro_xml(data)
        else:
            return self._map_from_world_xml(data)
    
    def _map_from_world_xml(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Mapira ASYCUDA World XML podatke."""
        # Osnovno mapiranje za World format
        mapped = {}
        
        if 'header' in data:
            header = data['header']
            # Mapiranje zaglavlja
            mapped['broj_deklaracije'] = header.get('broj_deklaracije', '')
            mapped['datum'] = header.get('datum', '')
            mapped['vrsta_deklaracije'] = header.get('vrsta_deklaracije', '')
            
            # Mapiranje izvoznika
            mapped['izvoznik_id'] = header.get('izvoznik_id', '')
            mapped['izvoznik_naziv'] = header.get('izvoznik_naziv', '')
        
        if 'items' in data:
            mapped['items'] = []
            for item in data['items']:
                mapped_item = {
                    'line_no': getattr(item, 'line_no', 0),
                    'naziv_robe': getattr(item, 'naziv_robe', ''),
                    'tarifni_broj': getattr(item, 'tarifni_broj', ''),
                    'zemlja_porijekla': getattr(item, 'zemlja_porijekla', ''),
                    'bruto_kg': getattr(item, 'bruto_kg', 0.0),
                    'neto_kg': getattr(item, 'neto_kg', 0.0),
                }
                mapped['items'].append(mapped_item)
        
        return mapped
    
    def _map_from_pro_xml(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Mapira ASYCUDA Pro XML podatke."""
        mapped = {}
        
        if 'header' in data:
            header = data['header']
            # Mapiranje zaglavlja za Pro format
            mapped['broj_deklaracije'] = header.get('broj_deklaracije', '')
            mapped['datum'] = header.get('datum', '')
            mapped['vrsta_deklaracije'] = header.get('vrsta_deklaracije', '')
            
            # Pro format koristi drugačija imena polja
            mapped['izvoznik_id'] = header.get('izvoznik_id', '')
            mapped['izvoznik_naziv'] = header.get('izvoznik_naziv', '')
            mapped['izvoznik_adresa'] = header.get('izvoznik_adresa', '')
            
            mapped['primalac_id'] = header.get('primalac_id', '')
            mapped['primalac_naziv'] = header.get('primalac_naziv', '')
            
            mapped['transport_id'] = header.get('transport_id', '')
            mapped['aktivno_transport'] = header.get('aktivno_transport', '')
        
        if 'items' in data:
            mapped['items'] = []
            for item in data['items']:
                mapped_item = {
                    'line_no': getattr(item, 'line_no', 0),
                    'naziv_robe': getattr(item, 'naziv_robe', ''),
                    'tarifni_broj': getattr(item, 'tarifni_broj', ''),
                    'zemlja_porijekla': getattr(item, 'zemlja_porijekla', ''),
                    'bruto_kg': getattr(item, 'bruto_kg', 0.0),
                    'neto_kg': getattr(item, 'neto_kg', 0.0),
                    'valuta': getattr(item, 'valuta', 'EUR'),
                }
                mapped['items'].append(mapped_item)
        
        mapped['format'] = 'pro'
        return mapped

    def map_to_asycuda_xml(self, draft: Any, format_type: str = "world") -> Dict[str, Any]:
        """
        Mapira Draft u ASYCUDA XML format.

        Args:
            draft: DeclarationDraft model
            format_type: Tip XML formata - "world" ili "pro"

        Returns:
            Podaci spremni za XML generisanje
        """
        if format_type.lower() == "pro":
            return self._map_to_pro_xml(draft)
        else:
            return self._map_to_world_xml(draft)
    
    def _map_to_world_xml(self, draft: Any) -> Dict[str, Any]:
        """Mapira Draft u World XML format."""
        # Ovo će biti implementirano korišćenjem postojećeg AsycudaXMLBuilder
        return {
            'broj_deklaracije': getattr(draft, 'broj_deklaracije', ''),
            'datum': getattr(draft, 'datum_prijema', ''),
            'vrsta_deklaracije': getattr(draft, 'vrsta_deklaracije', ''),
            'format': 'world'
        }
    
    def _map_to_pro_xml(self, draft: Any) -> Dict[str, Any]:
        """Mapira Draft u Pro XML format."""
        data = {
            'broj_deklaracije': getattr(draft, 'broj_deklaracije', ''),
            'datum': getattr(draft, 'datum_prijema', ''),
            'vrsta_deklaracije': getattr(draft, 'vrsta_deklaracije', ''),
            'izvoznik_id': getattr(draft, 'izvoznik_id', ''),
            'izvoznik_naziv': getattr(draft, 'izvoznik_naziv', ''),
            'izvoznik_adresa': getattr(draft, 'izvoznik_adresa', ''),
            'primalac_id': getattr(draft, 'primalac_id', ''),
            'primalac_naziv': getattr(draft, 'primalac_naziv', ''),
            'transport_id': getattr(draft, 'transport_id', ''),
            'aktivno_transport': getattr(draft, 'aktivno_transport', ''),
            'format': 'pro'
        }
        
        # Dodaj stavke ako postoje
        if hasattr(draft, 'items') and draft.items:
            data['items'] = []
            for item in draft.items:
                item_data = {
                    'naziv_robe': getattr(item, 'naziv_robe', ''),
                    'tarifni_broj': getattr(item, 'tarifni_broj', ''),
                    'zemlja_porijekla': getattr(item, 'zemlja_porijekla', ''),
                    'bruto_kg': getattr(item, 'bruto_kg', 0.0),
                    'neto_kg': getattr(item, 'neto_kg', 0.0),
                    'valuta': getattr(item, 'valuta', 'EUR'),
                }
                data['items'].append(item_data)
        
        return data
    
    def map_from_asycuda_pro(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mapira ASYCUDA Pro podatke u Draft format.
        
        Args:
            data: Sirovi Pro podaci
        
        Returns:
            Mapirani podaci
        """
        return self._map_from_pro_xml(data)
    
    def map_to_asycuda_pro(self, draft: Any) -> Dict[str, Any]:
        """
        Mapira Draft u ASYCUDA Pro format.
        
        Args:
            draft: DeclarationDraft model
        
        Returns:
            Podaci spremni za Pro XML generisanje
        """
        return self._map_to_pro_xml(draft)
    
    def convert_world_to_pro(self, world_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Konvertuje podatke iz World formata u Pro format.
        
        Args:
            world_data: Podaci u World formatu
        
        Returns:
            Podaci u Pro formatu
        """
        pro_data = {}
        
        # Mapiranje osnovnih polja
        if 'broj_deklaracije' in world_data:
            pro_data['broj_deklaracije'] = world_data['broj_deklaracije']
        
        if 'datum' in world_data:
            pro_data['datum'] = world_data['datum']
        
        if 'vrsta_deklaracije' in world_data:
            pro_data['vrsta_deklaracije'] = world_data['vrsta_deklaracije']
        
        # Mapiranje izvoznika
        if 'izvoznik_id' in world_data:
            pro_data['izvoznik_id'] = world_data['izvoznik_id']
        
        if 'izvoznik_naziv' in world_data:
            pro_data['izvoznik_naziv'] = world_data['izvoznik_naziv']
        
        # Mapiranje primaoca
        if 'primalac_id' in world_data:
            pro_data['primalac_id'] = world_data['primalac_id']
        
        if 'primalac_naziv' in world_data:
            pro_data['primalac_naziv'] = world_data['primalac_naziv']
        
        # Mapiranje stavki
        if 'items' in world_data:
            pro_data['items'] = []
            for item in world_data['items']:
                pro_item = {
                    'naziv_robe': item.get('naziv_robe', ''),
                    'tarifni_broj': item.get('tarifni_broj', ''),
                    'zemlja_porijekla': item.get('zemlja_porijekla', ''),
                    'bruto_kg': item.get('bruto_kg', 0.0),
                    'neto_kg': item.get('neto_kg', 0.0),
                    'valuta': item.get('valuta', 'EUR'),
                }
                pro_data['items'].append(pro_item)
        
        pro_data['format'] = 'pro'
        return pro_data
    
    def convert_pro_to_world(self, pro_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Konvertuje podatke iz Pro formata u World format.
        
        Args:
            pro_data: Podaci u Pro formatu
        
        Returns:
            Podaci u World formatu
        """
        world_data = {}
        
        # Mapiranje osnovnih polja
        if 'broj_deklaracije' in pro_data:
            world_data['broj_deklaracije'] = pro_data['broj_deklaracije']
        
        if 'datum' in pro_data:
            world_data['datum'] = pro_data['datum']
        
        if 'vrsta_deklaracije' in pro_data:
            world_data['vrsta_deklaracije'] = pro_data['vrsta_deklaracije']
        
        # Mapiranje izvoznika
        if 'izvoznik_id' in pro_data:
            world_data['izvoznik_id'] = pro_data['izvoznik_id']
        
        if 'izvoznik_naziv' in pro_data:
            world_data['izvoznik_naziv'] = pro_data['izvoznik_naziv']
        
        # Mapiranje stavki
        if 'items' in pro_data:
            world_data['items'] = []
            for item in pro_data['items']:
                world_item = {
                    'naziv_robe': item.get('naziv_robe', ''),
                    'tarifni_broj': item.get('tarifni_broj', ''),
                    'zemlja_porijekla': item.get('zemlja_porijekla', ''),
                    'bruto_kg': item.get('bruto_kg', 0.0),
                    'neto_kg': item.get('neto_kg', 0.0),
                }
                world_data['items'].append(world_item)
        
        world_data['format'] = 'world'
        return world_data
