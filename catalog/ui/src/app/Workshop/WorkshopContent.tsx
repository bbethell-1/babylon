import React, { useMemo } from 'react';
import yaml from 'js-yaml';
import {
  Bullseye,
  DescriptionList,
  DescriptionListDescription,
  DescriptionListGroup,
  DescriptionListTerm,
  PageSection,
  PageSectionVariants,
  Stack,
  StackItem,
  Title,
} from '@patternfly/react-core';
import ExternalLinkAltIcon from '@patternfly/react-icons/dist/js/icons/external-link-alt-icon';
import { renderContent } from '@app/util';
import EditorViewer from '@app/components/Editor/EditorViewer';
import Hero from '@app/components/Hero';
import heroImg from '@app/bgimages/hero-img.jpeg';
import { WorkshopDetails } from './workshopApi';

import './workshop-content.css';

const WorkshopContent: React.FC<{
  workshop: WorkshopDetails;
}> = ({ workshop }) => {
  const description = workshop.description;
  const displayName = workshop.displayName || 'Workshop';
  const userAssignment = workshop.assignment;
  let renderEditor = true;

  const userAssignmentMessagesHtml = useMemo(
    () =>
      userAssignment.messages ? (
        <div
          dangerouslySetInnerHTML={{
            __html: renderContent(userAssignment.messages.replace(/\n/g, '  +\n'), { format: 'asciidoc' }),
          }}
        />
      ) : null,
    [userAssignment.messages]
  );

  try {
    JSON.parse(description);
  } catch {
    renderEditor = false;
  }

  return (
    <PageSection variant={PageSectionVariants.light} className="workshop-content" padding={{ default: 'noPadding' }}>
      <Hero image={heroImg}>
        <Title headingLevel="h1" size="xl" style={{ fontSize: '40px' }}>
          <b>{displayName}</b>
        </Title>
      </Hero>
      <Stack hasGutter className="workshop-content__wrapper">
        <StackItem>
          <Bullseye>
            <Title headingLevel="h3" className="workshop-content__title">
              Instructions for {displayName}
            </Title>
          </Bullseye>
        </StackItem>
        {description ? (
          <StackItem className="workshop-content__description">
            <div>
              {renderEditor ? (
                <EditorViewer value={description} />
              ) : (
                <div dangerouslySetInnerHTML={{ __html: renderContent(description, { format: 'html' }) }} />
              )}
            </div>
          </StackItem>
        ) : null}
        <StackItem>
          <Bullseye>
            <DescriptionList isHorizontal>
              {userAssignment.labUserInterface ? (
                <DescriptionListGroup>
                  <DescriptionListTerm>Lab User Interface</DescriptionListTerm>
                  <DescriptionListDescription>
                    <a href={userAssignment.labUserInterface.url} target="_blank" rel="noreferrer">
                      {userAssignment.labUserInterface.url} <ExternalLinkAltIcon />
                    </a>
                  </DescriptionListDescription>
                </DescriptionListGroup>
              ) : null}
              {userAssignment.messages ? (
                <DescriptionListGroup>
                  <DescriptionListTerm>Messages</DescriptionListTerm>
                  <DescriptionListDescription>{userAssignmentMessagesHtml}</DescriptionListDescription>
                </DescriptionListGroup>
              ) : null}
              {userAssignment.data ? (
                <DescriptionListGroup>
                  <DescriptionListTerm>Data</DescriptionListTerm>
                  <DescriptionListDescription>
                    <pre>{yaml.dump(userAssignment.data)}</pre>
                  </DescriptionListDescription>
                </DescriptionListGroup>
              ) : null}
            </DescriptionList>
          </Bullseye>
        </StackItem>
      </Stack>
    </PageSection>
  );
};

export default WorkshopContent;
