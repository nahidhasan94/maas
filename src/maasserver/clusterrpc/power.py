# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers relating to nodes."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "power_off_node",
    "power_on_node",
]

from functools import partial

from maasserver.rpc import getClientFor
from provisioningserver.logger import get_maas_logger
from provisioningserver.rpc.cluster import (
    PowerOff,
    PowerOn,
)
from provisioningserver.utils.twisted import asynchronous


maaslog = get_maas_logger("power")


@asynchronous(timeout=15)
def power_node(command, system_id, hostname, cluster_uuid, power_info):
    """Power-on/off the given nodes.

    Nodes can be in any cluster; the power calls will be directed to their
    owning cluster.

    :param command: The `amp.Command` to call.
    :param system-id: The Node's system_id
    :param hostname: The Node's hostname
    :param cluster-uuid: The UUID of the cluster to which the Node is
        attached.
    :param power-info: A dict containing the power information for the
        node.
    :return: A :py:class:`twisted.internet.defer.Deferred` that will
        fire when the `command` call completes.

    """
    def call_power_command(client, **kwargs):
        return client(command, **kwargs)

    maaslog.debug("%s: Asking cluster to power on node.", hostname)
    d = getClientFor(cluster_uuid).addCallback(
        call_power_command, system_id=system_id, hostname=hostname,
        power_type=power_info.power_type,
        context=power_info.power_parameters)

    # We don't strictly care about the result _here_; the outcome of the
    # deferred gets reported elsewhere. However, PowerOn can return
    # UnknownPowerType and NotImplementedError which are worth knowing
    # about and returning to the caller of this API method, so it's
    # probably worth changing PowerOn (or adding another call) to return
    # after initial validation but then continue with the powering-on
    # process. For now we simply return the deferred to the caller so
    # they can choose to chain onto it, or to "cap it off", so that
    # result gets consumed (Twisted will complain if an error is not
    # consumed).
    return d


power_off_node = partial(power_node, PowerOff)
power_on_node = partial(power_node, PowerOn)
