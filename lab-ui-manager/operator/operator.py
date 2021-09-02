#!/usr/bin/env python3

import jinja2
import json
import kopf
import kubernetes
import os

from copy import deepcopy

anarchy_domain = os.environ.get('ANARCHY_DOMAIN', 'anarchy.gpte.redhat.com')
anarchy_api_version = os.environ.get('ANARCHY_API_VERSION', 'v1')
babylon_domain = os.environ.get('BABYLON_DOMAIN', 'babylon.gpte.redhat.com')
babylon_api_version = os.environ.get('BABYLON_API_VERSION', 'v1')
poolboy_domain = os.environ.get('POOLBOY_DOMAIN', 'poolboy.gpte.redhat.com')
poolboy_api_version = os.environ.get('POOLBOY_API_VERSION', 'v1')
poolboy_namespace = os.environ.get('POOLBOY_NAMESPACE', 'poolboy')

if os.path.exists('/run/secrets/kubernetes.io/serviceaccount'):
    kubernetes.config.load_incluster_config()
else:
    kubernetes.config.load_kube_config()

core_v1_api = kubernetes.client.CoreV1Api()
custom_objects_api = kubernetes.client.CustomObjectsApi()
j2env = jinja2.Environment(trim_blocks = True)

@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, **_):
    # Disable scanning for CustomResourceDefinitions
    settings.scanning.disabled = True

@kopf.on.event(poolboy_domain, poolboy_api_version, 'resourceclaims')
def resourceclaim_event(event, logger, **_):
    resource_claim = event.get('object')
    if not resource_claim \
    or resource_claim.get('kind') != 'ResourceClaim':
        logger.warning(event)
        return

    metadata = resource_claim.get('metadata')
    name = metadata.get('name')
    namespace = metadata.get('namespace')
    annotations = metadata.get('annotations', {})
    labels = metadata.get('labels', {})

    # Check catalog item to create for users if this is a multi-user environment
    user_catalog_item = labels.get(f"{babylon_domain}/userCatalogItem")

    # Check user catalog item value against namespace annotation
    namespace_obj = core_v1_api.read_namespace(namespace)
    allow_user_catalog_items = json.loads(namespace_obj.metadata.annotations.get(f"{babylon_domain}/allowUserCatalogItems", '[]'))
    if user_catalog_item \
    and user_catalog_item not in allow_user_catalog_items \
    and '*' not in allow_user_catalog_items:
        logger.warn(f"{babylon_domain}/userCatalogItem annotation set, but not allowed in this namespace")
        user_catalog_item = None

    bookbag_annotation = annotations.get(f"{babylon_domain}/bookbag")

    # Nothing to do if no configuration for bookbag or user catalog item
    if not bookbag_annotation and not user_catalog_item:
        return

    bookbag_config = json.loads(bookbag_annotation) if bookbag_annotation else None

    requester = annotations.get(f"{babylon_domain}/requester")

    resource_handle_ref = resource_claim.get('status', {}).get('resourceHandle')
    if not resource_handle_ref:
        return

    resource_handle = custom_objects_api.get_namespaced_custom_object(
        poolboy_domain, poolboy_api_version, poolboy_namespace, 'resourcehandles', resource_handle_ref['name']
    )
    resource_handle_ref['uid'] = resource_handle['metadata']['uid']
    resource_handle_ref['controller'] = True
    resource_handle_ref['blockOwnerDeletion'] = False

    resource_claim_ref = dict(
        apiVersion = resource_claim['apiVersion'],
        controller = True,
        blockOwnerDeletion = False,
        kind = resource_claim['kind'],
        name = name,
        uid = metadata['uid']
    )

    guid = resource_handle_ref['name'][5:]
    provision_data = {
        'guid': guid,
        'user': requester,
    }
    provision_messages = []
    users = {}

    if not 'status' in resource_claim:
        return
    if not resource_claim['status']['resources']:
        return
    for resource in resource_claim['status']['resources']:
        resource_state = resource.get('state')
        if not resource_state:
            return
        if resource_state['apiVersion'] != f"{anarchy_domain}/{anarchy_api_version}" \
        or resource_state['kind'] != 'AnarchySubject':
            continue
        spec_vars = resource_state.get('spec', {}).get('vars', {})
        if spec_vars.get('current_state') not in ['started', 'stopped']:
            return
        provision_data.update(spec_vars.get('provision_data', {}))
        provision_messages.extend(spec_vars.get('provision_messages', []))
        for user, user_data in provision_data.get('users', {}).items():
            if user in users:
                users[user].update(user_data)
            else:
                users[user] = user_data

    image_stream = None
    if bookbag_config and bookbag_config.get('imageBuild'):
        image_stream = 'bookbag-{0}'.format(guid)
        manage_bookbag_image_build(
            namespace,
            image_stream,
            bookbag_config,
            resource_claim_ref,
            logger,
        )

    resource_claim_patch = {}

    if users:
        lab_ui_urls = {}
        for user, user_data in users.items():
            user_data['guid'] = guid
            user_data['user'] = user
            if bookbag_config:
                bookbag_hostname = manage_bookbag_deployment(
                    namespace,
                    'bookbag-{0}-{1}'.format(guid, user),
                    bookbag_config,
                    user_data,
                    resource_claim_ref,
                    image_stream,
                    logger,
                )
                bookbag_url = f"https://{bookbag_hostname}/"
                lab_ui_urls[user] = bookbag_url
            elif 'bookbag_url' in user_data:
                lab_ui_urls[user] = user_data['bookbag_url']

            if user_catalog_item \
            and not annotations.get(f"{babylon_domain}/userResourceHandlesGenerated"):
                user_resource_handle = {
                    "apiVersion": f"{poolboy_domain}/{poolboy_api_version}",
                    "kind": "ResourceHandle",
                    "metadata": {
                        "name": f"guid-{guid}-{user}",
                        "ownerReferences": [resource_handle_ref],
                    },
                    "spec": {
                        "resources": [{
                            "provider": {
                                "apiVersion": f"{poolboy_domain}/{poolboy_api_version}",
                                "kind": "ResourceProvider",
                                "name": "babylon-user-configmap",
                                "namespace": "poolboy",
                            },
                            "template": {
                                "metadata": {
                                    "namespace": namespace,
                                    "labels": {
                                        f"{babylon_domain}/catalogItem": user_catalog_item,
                                    },
                                },
                                "data": {
                                    "userData": json.dumps(user_data),
                                }
                            }
                        }]
                    }
                }
                if lab_ui_urls.get(user):
                    user_resource_handle['spec']['resources'][0]['template']['data']['labUserInterfaceUrl'] = lab_ui_urls[user]
                try:
                    custom_objects_api.create_namespaced_custom_object(
                        poolboy_domain, poolboy_api_version, poolboy_namespace, 'resourcehandles', user_resource_handle
                    )
                except kubernetes.client.rest.ApiException as e:
                    if e.status == 409:
                        pass
                    else:
                        raise

                deepmerge(resource_claim_patch, {
                    "metadata": {
                        "annotations": {
                            f"{babylon_domain}/userResourceHandlesGenerated": "true",
                        }
                    }
                })

        if lab_ui_urls:
            lab_ui_urls = json.dumps(lab_ui_urls)
            if lab_ui_urls != annotations.get(f"{babylon_domain}/labUserInterfaceUrls"):
                deepmerge(resource_claim_patch, {
                    "metadata": {
                        "annotations": {
                            f"{babylon_domain}/labUserInterfaceUrls": lab_ui_urls,
                        }
                    }
                })

    elif bookbag_config:
        if provision_messages:
            provision_data['user_info_messages'] = "\n".join(provision_messages)
        bookbag_hostname = manage_bookbag_deployment(
            namespace,
            'bookbag-{0}'.format(guid),
            bookbag_config,
            provision_data,
            resource_claim_ref,
            image_stream,
            logger,
        )
        bookbag_url = f"https://{bookbag_hostname}/"
        if bookbag_url != annotations.get(f"{babylon_domain}/labUserInterfaceUrl"):
            deepmerge(resource_claim_patch, {
                "metadata": {
                    "annotations": {
                        f"{babylon_domain}/labUserInterfaceUrl": bookbag_url,
                    }
                }
            })

    if resource_claim_patch:
        custom_objects_api.patch_namespaced_custom_object(
            poolboy_domain, poolboy_api_version, namespace, "resourceclaims", name, resource_claim_patch
        )

def deepmerge(d, s):
    if isinstance(d, dict) and isinstance(s, dict):
        for k, v in s.items():
            if k in d:
                if isinstance(v, dict) and isinstance(d[k], dict) \
                or isinstance(v, list) and isinstance(d[k], list):
                    deepmerge(d[k], v)
                else:
                    d[k] = deepcopy(v)
            else:
                d[k] = deepcopy(v)
    elif isinstance(d, list) and isinstance(s, list):
        for i, v in enumerate(s):
            if i < len(d):
                if isinstance(v, dict) and isinstance(d[i], dict) \
                or isinstance(v, list) and isinstance(d[i], list):
                    deepmerge(d[i], v)
                else:
                    d[i] = deepcopy(v)
            else:
                d[i] = deepcopy(v)
    else:
        raise Exception('Invalid types to deepmerge')

    return d

def get_build_config(namespace, name):
    try:
        return custom_objects_api.get_namespaced_custom_object(
            'build.openshift.io', 'v1', namespace, 'buildconfigs', name
        )
    except kubernetes.client.rest.ApiException as e:
        if e.status == 404:
            return None
        else:
            raise

def get_deployment(namespace, name):
    try:
        return custom_objects_api.get_namespaced_custom_object(
            'apps', 'v1', namespace, 'deployments', name
        )
    except kubernetes.client.rest.ApiException as e:
        if e.status == 404:
            return None
        else:
            raise

def get_image_stream(namespace, name):
    try:
        return custom_objects_api.get_namespaced_custom_object(
            'image.openshift.io', 'v1', namespace, 'imagestreams', name
        )
    except kubernetes.client.rest.ApiException as e:
        if e.status == 404:
            return None
        else:
            raise

def get_role_binding(namespace, name):
    try:
        return custom_objects_api.get_namespaced_custom_object(
            'rbac.authorization.k8s.io', 'v1', namespace, 'rolebindings', name
        )
    except kubernetes.client.rest.ApiException as e:
        if e.status == 404:
            return None
        else:
            raise

def get_route(namespace, name):
    try:
        return custom_objects_api.get_namespaced_custom_object(
            'route.openshift.io', 'v1', namespace, 'routes', name
        )
    except kubernetes.client.rest.ApiException as e:
        if e.status == 404:
            return None
        else:
            raise

def get_service(namespace, name):
    try:
        return core_v1_api.read_namespaced_service(name, namespace)
    except kubernetes.client.rest.ApiException as e:
        if e.status == 404:
            return None
        else:
            raise

def get_service_account(namespace, name):
    try:
        return core_v1_api.read_namespaced_service_account(name, namespace)
    except kubernetes.client.rest.ApiException as e:
        if e.status == 404:
            return None
        else:
            raise

def manage_bookbag_image_build(namespace, name, bookbag_config, owner_ref, logger=None):
    """
    Create BuildConfig and ImageStream to build Bookbag image.
    """
    build_spec = deepcopy(bookbag_config['imageBuild'])
    build_spec['output'] = {
        "to": {
            "kind": "ImageStreamTag",
            "name": f"{name}:latest",
        }
    }
    if 'strategy' not in build_spec:
        build_spec['strategy'] = {
            "type": "Source",
            "sourceStrategy": {
                "from": {
                    "kind": "DockerImage",
                    "name": "quay.io/openshifthomeroom/workshop-dashboard:5.0.0",
                }
            }
        }
    build_spec['triggers'] = [{"type": "ConfigChange"}]

    image_stream = get_image_stream(namespace, name)
    if not image_stream:
        custom_objects_api.create_namespaced_custom_object(
            'image.openshift.io', 'v1', namespace, 'imagestreams',
            {
                "apiVersion": "image.openshift.io/v1",
                "kind": "ImageStream",
                "metadata": {
                    "name": name,
                    "namespace": namespace,
                    "ownerReferences": [owner_ref],
                },
            }
        )

    build_config = get_build_config(namespace, name)
    if build_config:
        merged_spec = deepmerge(deepcopy(build_config['spec']), build_spec)
        if merged_spec != build_config['spec']:
            try:
                custom_objects_api.replace_namespaced_custom_object(
                    'build.openshift.io', 'v1', namespace, 'buildconfigs', name, {
                        "apiVersion": "build.openshift.io/v1",
                        "kind": "BuildConfig",
                        "metadata": build_config['metadata'],
                        "spec": merged_spec,
                    }
                )
            except kubernetes.client.rest.ApiException as e:
                if e.status == 409:
                    pass
                else:
                    raise
    else:
        custom_objects_api.create_namespaced_custom_object(
            'build.openshift.io', 'v1', namespace, 'buildconfigs',
            {
                "apiVersion": "build.openshift.io/v1",
                "kind": "BuildConfig",
                "metadata": {
                    "name": name,
                    "namespace": namespace,
                    "ownerReferences": [owner_ref],
                },
                "spec": build_spec,
            }
        )

def manage_bookbag_deployment(namespace, name, bookbag_config, bookbag_vars, owner_ref, image_stream=None, logger=None):
    """
    Create Deployment, RoleBinding, Route, Service, ServiceAccount for bookbag.
    """
    auth = bookbag_config.get('auth', {})
    auth_user = auth.get('user', '*')
    auth_password = auth.get('password', '')
    image = bookbag_config.get('image')

    service_account = get_service_account(namespace, name)
    if not service_account:
        core_v1_api.create_namespaced_service_account(
            namespace,
            {
                "apiVersion": "v1",
                "kind": "ServiceAccount",
                "metadata": {
                    "name": name,
                    "ownerReferences": [owner_ref],
                }
            }
        )


    role_binding = get_role_binding(namespace, name)
    if not role_binding:
        custom_objects_api.create_namespaced_custom_object(
            'rbac.authorization.k8s.io', 'v1', namespace, 'rolebindings',
            {
                "apiVersion": "rbac.authorization.k8s.io/v1",
                "kind": "RoleBinding",
                "metadata": {
                    "name": name,
                    "ownerReferences": [owner_ref],
                },
                "roleRef": {
                    "apiGroup": "rbac.authorization.k8s.io",
                    "kind": "ClusterRole",
                    "name": "basic-user",
                },
                "subjects": [{
                    "kind": "ServiceAccount",
                    "name": name,
                    "namespace": namespace,
                }]
            }
        )

    deployment = get_deployment(namespace, name)
    deployment_spec = {
        "replicas": 1,
        "selector": {
            "matchLabels": {
                "name": name,
            }
        },
        "strategy": {
            "type": "Recreate",
        },
        "template": {
            "metadata": {
                "labels": {
                    "name": name,
                }
            },
            "spec": {
                "containers": [{
                    "name": "bookbag",
                    "env": [{
                        "name": "APPLICATION_NAME",
                        "value": name,
                    }, {
                        "name": "AUTH_USERNAME",
                        "value": auth_user,
                    }, {
                        "name": "AUTH_PASSWORD",
                        "value": auth_password,
                    }, {
                        "name": "CLUSTER_SUBDOMAIN",
                    }, {
                        "name": "OAUTH_SERVICE_ACCOUNT",
                        "value": name,
                    }, {
                        "name": "DOWNLOAD_URL",
                    }, {
                        "name": "WORKSHOP_FILE",
                    }, {
                        "name": "OC_VERSION",
                    }, {
                        "name": "ODO_VERSION",
                    }, {
                        "name": "KUBECTL_VERSION",
                    }, {
                        "name": "WORKSHOP_VARS",
                        "value": json.dumps(bookbag_vars),
                    }],
                    "imagePullPolicy": "Always",
                    "ports": [{
                        "containerPort": 10080,
                    }],
                    "resources": {},
                }],
                "serviceAccountName": name,
            }
        }
    }
    # If using image stream then image value is dynamic
    if not image_stream:
        deployment_spec['template']['spec']['containers']['image'] = image
    if deployment:
        merged_spec = deepmerge(deepcopy(deployment['spec']), deployment_spec)
        if merged_spec != deployment['spec']:
            try:
                custom_objects_api.replace_namespaced_custom_object(
                    'apps', 'v1', namespace, 'deployments', name, {
                        "apiVersion": "apps/v1",
                        "kind": "Deployment",
                        "metadata": deployment['metadata'],
                        "spec": merged_spec,
                    }
                )
            except kubernetes.client.rest.ApiException as e:
                if e.status == 409:
                    pass
                else:
                    raise
    else:
        deployment_meta = {
            "name": name,
            "namespace": namespace,
            "ownerReferences": [owner_ref],
        }

        if image_stream:
            # Set image-change trigger on image stream
            deployment_meta['annotations'] = {
                "image.openshift.io/triggers": json.dumps([{
                    "from": {
                        "kind": "ImageStreamTag",
                        "name": f"{image_stream}:latest",
                    },
                    "fieldPath": 'spec.template.spec.containers[?(@.name=="bookbag")].image',
                }])
            }
            # This is image value is just a place-holder, required for validation
            deployment_spec['template']['spec']['containers'][0]['image'] = \
                f"image-registry.openshift-image-registry.svc:5000/{namespace}/{image_stream}:latest"

        custom_objects_api.create_namespaced_custom_object(
            'apps', 'v1', namespace, 'deployments',
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": deployment_meta,
                "spec": deployment_spec,
            }
        )

    service = get_service(namespace, name)
    if not service:
        core_v1_api.create_namespaced_service(
            namespace,
            {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": {
                    "name": name,
                    "namespace": namespace,
                    "ownerReferences": [owner_ref],
                },
                "spec": {
                    "ports": [{
                        "name": "10080-tcp",
                        "port": 10080,
                        "protocol": "TCP",
                        "targetPort": 10080,
                    }],
                    "selector": {
                        "name": name,
                    },
                    "type": "ClusterIP",
                }
            }
        )

    route = get_route(namespace, name)
    if not route:
        route = custom_objects_api.create_namespaced_custom_object(
            'route.openshift.io', 'v1', namespace, 'routes',
            {
                "apiVersion": "route.openshift.io/v1",
                "kind": "Route",
                "metadata": {
                    "name": name,
                    "namespace": namespace,
                    "ownerReferences": [owner_ref],
                },
                "spec": {
                    "port": {
                        "targetPort": "10080-tcp",
                    },
                    "tls": {
                        "insecureEdgeTerminationPolicy": "Redirect",
                        "termination": "edge",
                    },
                    "to": {
                        "kind": "Service",
                        "name": name,
                    },
                }
            }
        )
    return route['spec']['host']
