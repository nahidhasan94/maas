# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for power parameters."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from django import forms
import jsonschema
from maasserver.clusterrpc import power_parameters
from maasserver.clusterrpc.power_parameters import (
    add_power_type_parameters,
    get_power_type_parameters,
    get_power_type_parameters_from_json,
    get_power_types,
    JSON_POWER_TYPE_SCHEMA,
    make_form_field,
    POWER_TYPE_PARAMETER_FIELD_SCHEMA,
)
from maasserver.config_forms import DictCharField
from maasserver.fields import MACAddressFormField
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.forms import compose_invalid_choice_text
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from mock import sentinel
from provisioningserver.power.poweraction import PowerAction
from provisioningserver.power_schema import (
    JSON_POWER_TYPE_PARAMETERS,
    make_json_field,
)


class TestPowerActionRendering(MAASServerTestCase):
    """Test that the power templates can be rendered."""

    scenarios = [
        (type['name'], {'power_type': type['name']})
        for type in JSON_POWER_TYPE_PARAMETERS
    ]

    def make_random_parameters(self, power_change="on"):
        params = {'power_change': power_change}
        param_definition = get_power_type_parameters()[self.power_type]
        for name, field in param_definition.field_dict.items():
            params[name] = factory.make_name(name)
        return params

    def test_render_template(self):
        params = self.make_random_parameters()
        node = factory.make_Node(power_type=self.power_type)
        params.update(node.get_effective_power_parameters())
        # ip_address is determined by querying the ARP cache,
        # hence in this test the value does not matter.
        params.update(ip_address=factory.make_ipv4_address())
        # power_off_mode is provided via the API, and isn't a
        # built in parameter.
        params.update(power_off_mode=factory.make_name('power_off_mode'))
        action = PowerAction(self.power_type)
        script = action.render_template(
            action.get_template(), action.update_context(params))
        # The real check is that the rendering went fine.
        self.assertIsInstance(script, bytes)


class TestGetPowerTypeParametersFromJSON(MAASServerTestCase):
    """Test that get_power_type_parametrs_from_json."""

    def test_validates_json_power_type_parameters(self):
        invalid_parameters = [{
            'name': 'invalid_power_type',
            'fields': 'nothing to see here',
        }]
        self.assertRaises(
            jsonschema.ValidationError, get_power_type_parameters_from_json,
            invalid_parameters)

    def test_includes_empty_power_type(self):
        json_parameters = [{
            'name': 'something',
            'description': 'Meaningless',
            'fields': [{
                'name': 'some_field',
                'label': 'Some Field',
                'field_type': 'string',
                'required': False,
            }],
        }]
        power_type_parameters = get_power_type_parameters_from_json(
            json_parameters)
        self.assertEqual(['', 'something'], power_type_parameters.keys())

    def test_creates_dict_char_fields(self):
        json_parameters = [{
            'name': 'something',
            'description': 'Meaningless',
            'fields': [{
                'name': 'some_field',
                'label': 'Some Field',
                'field_type': 'string',
                'required': False,
            }],
        }]
        power_type_parameters = get_power_type_parameters_from_json(
            json_parameters)
        for name, field in power_type_parameters.items():
            self.assertIsInstance(field, DictCharField)


class TestMakeFormField(MAASServerTestCase):
    """Test that make_form_field() converts JSON fields to Django."""

    def test_creates_char_field_for_strings(self):
        json_field = {
            'name': 'some_field',
            'label': 'Some Field',
            'field_type': 'string',
            'required': False,
        }
        django_field = make_form_field(json_field)
        self.assertIsInstance(django_field, forms.CharField)

    def test_creates_choice_field_for_choices(self):
        json_field = {
            'name': 'some_field',
            'label': 'Some Field',
            'field_type': 'choice',
            'choices': [
                ['choice-one', 'Choice One'],
                ['choice-two', 'Choice Two'],
            ],
            'default': 'choice-one',
            'required': False,
        }
        django_field = make_form_field(json_field)
        self.assertIsInstance(django_field, forms.ChoiceField)
        self.assertEqual(json_field['choices'], django_field.choices)
        invalid_msg = compose_invalid_choice_text(
            json_field['name'], json_field['choices'])
        self.assertEqual(
            invalid_msg, django_field.error_messages['invalid_choice'])
        self.assertEqual(json_field['default'], django_field.initial)

    def test_creates_mac_address_field_for_mac_addresses(self):
        json_field = {
            'name': 'some_field',
            'label': 'Some Field',
            'field_type': 'mac_address',
            'required': False,
        }
        django_field = make_form_field(json_field)
        self.assertIsInstance(django_field, MACAddressFormField)

    def test_sets_properties_on_form_field(self):
        json_field = {
            'name': 'some_field',
            'label': 'Some Field',
            'field_type': 'string',
            'required': False,
        }
        django_field = make_form_field(json_field)
        self.assertEqual(
            (json_field['label'], json_field['required']),
            (django_field.label, django_field.required))


class TestMakeJSONField(MAASServerTestCase):
    """Test that make_json_field() creates JSON-verifiable fields."""

    def test_returns_json_verifiable_dict(self):
        json_field = make_json_field('some_field', 'Some Label')
        jsonschema.validate(json_field, POWER_TYPE_PARAMETER_FIELD_SCHEMA)

    def test_provides_sane_default_values(self):
        json_field = make_json_field('some_field', 'Some Label')
        expected_field = {
            'name': 'some_field',
            'label': 'Some Label',
            'required': False,
            'field_type': 'string',
            'choices': [],
            'default': '',
        }
        self.assertEqual(expected_field, json_field)

    def test_sets_field_values(self):
        expected_field = {
            'name': 'yet_another_field',
            'label': 'Can I stop writing tests now?',
            'required': True,
            'field_type': 'string',
            'choices': [
                ['spam', 'Spam'],
                ['eggs', 'Eggs'],
            ],
            'default': 'spam',
        }
        json_field = make_json_field(**expected_field)
        self.assertEqual(expected_field, json_field)

    def test_validates_choices(self):
        self.assertRaises(
            jsonschema.ValidationError, make_json_field,
            'some_field', 'Some Label', choices="Nonsense")


class TestAddPowerTypeParameters(MAASServerTestCase):

    def make_field(self):
        return make_json_field(
            self.getUniqueString(), self.getUniqueString())

    def test_adding_existing_types_is_a_no_op(self):
        existing_parameters = [{
            'name': 'blah',
            'description': 'baz',
            'fields': {},
        }]
        add_power_type_parameters(
            name='blah', description='baz', fields=[self.make_field()],
            parameters_set=existing_parameters)
        self.assertEqual(
            [{'name': 'blah', 'description': 'baz', 'fields': {}}],
            existing_parameters)

    def test_adds_new_power_type_parameters(self):
        existing_parameters = []
        fields = [self.make_field()]
        add_power_type_parameters(
            name='blah', description='baz', fields=fields,
            parameters_set=existing_parameters)
        self.assertEqual(
            [{'name': 'blah', 'description': 'baz', 'fields': fields}],
            existing_parameters)

    def test_validates_new_parameters(self):
        self.assertRaises(
            jsonschema.ValidationError, add_power_type_parameters,
            name='blah', description='baz', fields=[{}],
            parameters_set=[])

    def test_subsequent_parameters_set_is_valid(self):
        parameters_set = []
        fields = [self.make_field()]
        add_power_type_parameters(
            name='blah', description='baz', fields=fields,
            parameters_set=parameters_set)
        jsonschema.validate(
            parameters_set, JSON_POWER_TYPE_SCHEMA)


class TestPowerTypes(MAASTestCase):
    # This is deliberately not using a MAASServerTestCase as that
    # patches the get_all_power_types_from_clusters() function with data
    # that's hidden from tests in here.  Instead the tests patch
    # explicitly here.

    def test_get_power_types_transforms_data_to_dict(self):
        mocked = self.patch(
            power_parameters, "get_all_power_types_from_clusters")
        mocked.return_value = [
            {
                "name": "namevalue",
                "description": "descvalue",
            },
            {
                "name": "namevalue2",
                "description": "descvalue2",
            },
        ]
        expected = {
            "namevalue": "descvalue",
            "namevalue2": "descvalue2",
            }
        self.assertEqual(expected, get_power_types())

    def test_get_power_types_passes_args_through(self):
        mocked = self.patch(
            power_parameters, "get_all_power_types_from_clusters")
        mocked.return_value = []
        get_power_types(sentinel.nodegroup, sentinel.ignore_errors)
        self.assertThat(
            mocked, MockCalledOnceWith(
                sentinel.nodegroup, sentinel.ignore_errors))
