// Source: data/benchmarks/sv-benchmarks/loop-invgen/sendmail-close-angle.c
extern int unknown_int(void);

/*@
  requires bufferlen >1;
  requires inlen > 0;
  requires bufferlen < inlen;
*/
void loopy_367(int inlen, int bufferlen)
{
  int in;
  
  
  int buf;
  int buflim;

  
  
  

  buf = 0;
  in = 0;
  buflim = bufferlen - 2;

  while (unknown_int())
  {
    if (buf == buflim)
      break;
    {;
//@ assert(0<=buf);
}

    {;
//@ assert(buf<bufferlen);
}
 
    buf++;
out:
    in++;
    {;
//@ assert(0<=in);
}

    {;
//@ assert(in<inlen);
}

  }

    {;
//@ assert(0<=buf);
}

    {;
//@ assert(buf<bufferlen);
}

    buf++;

  {;
//@ assert(0<=buf);
}

  {;
//@ assert(buf<bufferlen);
}

  buf++;

 END:  return;
}