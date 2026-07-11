// Source: data/benchmarks/LinearArbitrary-SeaHorn/invgen/sendmail-mime-fromqp.c
extern int unknown(void);

extern int unknown();

/*@
  requires outfilelen > 0;
*/
void loopy_37(int outfilelen)
{
  
  
  int nchar = 0;

  int out = 0; 

  

  while(unknown())
  {
    
    if(unknown())
    {
      
      if(unknown())
	
	goto AFTERLOOP; 

      if(unknown())
      {
	out = 0;
	nchar = 0;
	goto LOOPEND;
      }
      else
      {
	
	if(unknown())  goto AFTERLOOP;

	nchar++;
	if (nchar >= outfilelen)
	  goto AFTERLOOP;

	{;
//@ assert(0<=out);
}

	{;
//@ assert(out<outfilelen);
}

	out++;
      }
    }
    else
    {
      
      nchar++;
      if (nchar >= outfilelen)
	goto AFTERLOOP;

      {;
//@ assert(0<=out);
}

      {;
//@ assert(out<outfilelen);
}

      out++;

      if(unknown()) goto AFTERLOOP;
    }
  LOOPEND:;
  }
 AFTERLOOP:

  {;
//@ assert(0<=out);
}

  {;
//@ assert(out<outfilelen);
}

  out++;
 RETURN:  return;
}