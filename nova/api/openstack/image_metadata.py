# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 OpenStack LLC.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from webob import exc

from nova import flags
from nova import image
from nova import quota
from nova import utils
from nova.api.openstack import common 
from nova.api.openstack import faults
from nova.api.openstack import wsgi


FLAGS = flags.FLAGS


class Controller(object):
    """The image metadata API controller for the Openstack API"""

    def __init__(self):
        self.image_service = image.get_default_image_service()

    def _get_metadata(self, context, image_id, image=None):
        if not image:
            image = self.image_service.show(context, image_id)
        metadata = image.get('properties', {})
        return metadata

    def _check_quota_limit(self, context, metadata):
        if metadata is None:
            return
        num_metadata = len(metadata)
        quota_metadata = quota.allowed_metadata_items(context, num_metadata)
        if quota_metadata < num_metadata:
            expl = _("Image metadata limit exceeded")
            raise exc.HTTPBadRequest(explanation=expl)

    def index(self, req, image_id):
        """Returns the list of metadata for a given instance"""
        context = req.environ['nova.context']
        metadata = self._get_metadata(context, image_id)
        return dict(metadata=metadata)

    def show(self, req, image_id, id):
        context = req.environ['nova.context']
        metadata = self._get_metadata(context, image_id)
        if id in metadata:
            return {'meta': {id: metadata[id]}}
        else:
            return faults.Fault(exc.HTTPNotFound())

    def create(self, req, image_id, body):
        context = req.environ['nova.context']
        img = self.image_service.show(context, image_id)
        metadata = self._get_metadata(context, image_id, img)
        if 'metadata' in body:
            for key, value in body['metadata'].iteritems():
                metadata[key] = value
        self._check_quota_limit(context, metadata)
        img['properties'] = metadata
        self.image_service.update(context, image_id, img, None)
        return dict(metadata=metadata)

    def update(self, req, image_id, id, body):
        context = req.environ['nova.context']

        try:
            meta = body['meta']
        except KeyError:
            expl = _('Incorrect request body format')
            raise exc.HTTPBadRequest(explanation=expl)

        if not id in meta:
            expl = _('Request body and URI mismatch')
            raise exc.HTTPBadRequest(explanation=expl)
        if len(meta) > 1:
            expl = _('Request body contains too many items')
            raise exc.HTTPBadRequest(explanation=expl)
        img = self.image_service.show(context, image_id)
        metadata = self._get_metadata(context, image_id, img)
        metadata[id] = meta[id]
        self._check_quota_limit(context, metadata)
        img['properties'] = metadata
        self.image_service.update(context, image_id, img, None)

        return req.body

    def delete(self, req, image_id, id):
        context = req.environ['nova.context']
        img = self.image_service.show(context, image_id)
        metadata = self._get_metadata(context, image_id)
        if not id in metadata:
            return faults.Fault(exc.HTTPNotFound())
        metadata.pop(id)
        img['properties'] = metadata
        self.image_service.update(context, image_id, img, None)


def create_resource():
    body_serializers = {
        'application/xml': common.MetadataXMLSerializer(),
    }
    serializer = wsgi.ResponseSerializer(body_serializers)

    return wsgi.Resource(Controller(), serializer=serializer)
