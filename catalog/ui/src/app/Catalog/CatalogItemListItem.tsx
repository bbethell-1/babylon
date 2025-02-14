import React from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import { Badge, Card, CardBody, CardHeader, Title } from '@patternfly/react-core';
import { CatalogItem } from '@app/types';
import StatusPageIcons from '@app/components/StatusPageIcons';
import { displayName, renderContent, stripHtml } from '@app/util';
import StarRating from '@app/components/StarRating';
import CatalogItemIcon from './CatalogItemIcon';
import {
  formatString,
  getDescription,
  getIsDisabled,
  getProvider,
  getRating,
  getStage,
  getStatus,
} from './catalog-utils';

import './catalog-item-list-item.css';

const CatalogItemListItem: React.FC<{ catalogItem: CatalogItem }> = ({ catalogItem }) => {
  const location = useLocation();
  const { namespace } = useParams();
  const urlSearchParams = new URLSearchParams(location.search);
  const { description, descriptionFormat } = getDescription(catalogItem);
  const provider = getProvider(catalogItem);
  const stage = getStage(catalogItem);
  const isDisabled = getIsDisabled(catalogItem);
  const rating = getRating(catalogItem);
  const { code: status } = getStatus(catalogItem);

  if (!urlSearchParams.has('item')) {
    if (namespace) {
      urlSearchParams.set('item', catalogItem.metadata.name);
    } else {
      urlSearchParams.set('item', `${catalogItem.metadata.namespace}/${catalogItem.metadata.name}`);
    }
  }

  return (
    <Link
      className={`catalog-item-list-item${isDisabled ? ' catalog-item-list-item--disabled' : ''}`}
      to={`${location.pathname}?${urlSearchParams.toString()}`}
    >
      <Card className="catalog-item-list-item__card" component="div">
        <CardHeader className="catalog-item-list-item__header">
          <CatalogItemIcon catalogItem={catalogItem} />
          {status && status !== 'operational' ? (
            <StatusPageIcons status={status} className="catalog-item-list-item__statusPageIcon" />
          ) : null}
          {stage === 'dev' ? (
            <Badge className="catalog-item-list-item__badge--dev">development</Badge>
          ) : stage === 'test' ? (
            <Badge className="catalog-item-list-item__badge--test">test</Badge>
          ) : stage === 'event' ? (
            <Badge className="catalog-item-list-item__badge--event">event</Badge>
          ) : null}
        </CardHeader>
        <CardBody className="catalog-item-list-item__body">
          <Title className="catalog-item-list-item__title" headingLevel="h3">
            {displayName(catalogItem)}
          </Title>
          <Title className="catalog-item-list-item__subtitle" headingLevel="h6">
            provided by {formatString(provider)}
          </Title>
          {description ? (
            <div className="catalog-item-card__description">
              {stripHtml(renderContent(description, { format: descriptionFormat })).slice(0, 150)}
            </div>
          ) : null}
          <div className="catalog-item-card__rating">
            <StarRating count={5} rating={rating?.ratingScore} total={rating?.totalRatings} readOnly hideIfNotRated />
          </div>
        </CardBody>
      </Card>
    </Link>
  );
};

export default CatalogItemListItem;
