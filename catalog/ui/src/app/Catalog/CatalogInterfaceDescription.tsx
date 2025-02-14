import React from 'react';
import { useSelector } from 'react-redux';

import { PageSection, PageSectionVariants, Title } from '@patternfly/react-core';

import { selectInterface } from '@app/store';

const CatalogInterfaceDescription: React.FC = () => {
  const userInterface = useSelector(selectInterface);

  if (userInterface === 'rhpds') {
    return (
      <PageSection variant={PageSectionVariants.light} style={{ paddingBottom: 0 }}>
        <Title headingLevel="h1" size="2xl">
          Red Hat Demo Platform
        </Title>
        <div>Select an item to request a new service, demo, or lab.</div>
      </PageSection>
    );
  } else if (userInterface === 'summit') {
    return (
      <PageSection variant={PageSectionVariants.light} style={{ paddingBottom: 0 }}>
        <Title headingLevel="h1" size="2xl">
          Red Hat Summit Labs
        </Title>
        <div>Please select the catalog item for your lab as instructed by a lab facilitator.</div>
      </PageSection>
    );
  } else {
    return (
      <PageSection variant={PageSectionVariants.light} style={{ paddingBottom: 0 }}>
        <Title headingLevel="h1" size="2xl">
          Catalog
        </Title>
        <div>Select an item to request a new service, demo, or lab.</div>
      </PageSection>
    );
  }
};

export default CatalogInterfaceDescription;
