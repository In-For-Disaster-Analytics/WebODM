from django.test import SimpleTestCase, override_settings
from unittest.mock import patch

from app.services import tas_allocations


class TASAllocationsTest(SimpleTestCase):
    @override_settings(
        TAS_RESOURCE_FILTER=['LS6', 'Lonestar6'],
        TAS_DEFAULT_ALLOCATION='PT2050-DataX',
    )
    @patch('app.services.tas_allocations._projects_for_user')
    def test_lists_active_allocations_and_prefers_default(self, projects_for_user):
        projects_for_user.return_value = [
            {
                'chargeCode': 'OTHER',
                'title': 'Other Project',
                'allocations': [
                    {
                        'resource': 'LS6',
                        'status': 'Active',
                        'computeAllocated': 100,
                        'computeUsed': 1,
                    }
                ],
            },
            {
                'chargeCode': 'PT2050-DataX',
                'title': 'Default Project',
                'allocations': [
                    {
                        'resource': 'Lonestar6',
                        'status': 'Active',
                        'computeAllocated': 100,
                        'computeUsed': 10,
                    }
                ],
            },
            {
                'chargeCode': 'INACTIVE',
                'title': 'Inactive Project',
                'allocations': [
                    {
                        'resource': 'LS6',
                        'status': 'Inactive',
                    }
                ],
            },
            {
                'chargeCode': 'WRONGRESOURCE',
                'title': 'Wrong Resource Project',
                'allocations': [
                    {
                        'resource': 'Frontera',
                        'status': 'Active',
                    }
                ],
            },
        ]

        allocations = tas_allocations.list_active_allocations('wmobley')

        self.assertEqual([a['chargeCode'] for a in allocations], ['OTHER', 'PT2050-DataX'])
        self.assertEqual(tas_allocations.choose_default_allocation(allocations), 'PT2050-DataX')

    @override_settings(TAS_DEFAULT_ALLOCATION='PT2050-DataX')
    def test_default_falls_back_to_first_allocation(self):
        allocations = [{'chargeCode': 'FIRST'}, {'chargeCode': 'SECOND'}]
        self.assertEqual(tas_allocations.choose_default_allocation(allocations), 'FIRST')
