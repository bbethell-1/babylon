import React from 'react';
import { PageHeader } from '@patternfly/react-core';
import UserInterfaceLogo from '@app/components/UserInterfaceLogo';
import summitLogo from '@app/bgimages/Summit-Logo.svg';
import RedHatLogo from '@app/components/RedHatLogo';

const WorkshopHeader: React.FC<{ userInterface: string }> = ({ userInterface }) => {
  function LogoImg() {
    if (userInterface === 'summit') {
      return (
        <button
          onClick={(ev: React.FormEvent<HTMLButtonElement>) => {
            ev.stopPropagation();
            window.open('https://summit.demo.redhat.com/');
          }}
          style={{ display: 'flex', width: '70px', border: 0, backgroundColor: 'transparent' }}
        >
          <img src={summitLogo} alt="Red Hat Summit" />
        </button>
      );
    }
    return (
      <span style={{ width: '278px', display: 'flex' }}>
        <UserInterfaceLogo />
      </span>
    );
  }
  return (
    <div style={{ backgroundColor: 'var(--pf-c-page__header--BackgroundColor)', gridArea: 'header' }}>
      <PageHeader
        className="workshop"
        logo={<LogoImg />}
        style={{ maxWidth: '1170px', margin: '0 auto', width: '100%' }}
        headerTools={
          userInterface === 'summit' ? (
            <a href="https://redhat.com/" style={{ width: '138px', marginLeft: 'auto', display: 'flex' }}>
              <RedHatLogo title="Red Hat" />
            </a>
          ) : null
        }
      ></PageHeader>
    </div>
  );
};

export default WorkshopHeader;
